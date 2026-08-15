"""Unit tests for MCP server preloading and error handling."""

import asyncio
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opscode.mcp.mcp_info import MCPServerInfo, MCPToolInfo
from opscode.mcp.preload import _probe_one_server, preload_mcp_server_info


@pytest.mark.asyncio
async def test_probe_one_server_success():
    """Test successful MCP server probing."""
    mock_session = AsyncMock()
    mock_tool = MagicMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "A test tool"
    mock_tool.inputSchema = {"type": "object"}
    mock_resp = MagicMock()
    mock_resp.tools = [mock_tool]
    mock_session.list_tools.return_value = mock_resp

    with patch("opscode.mcp.preload.AsyncExitStack") as mock_stack_cls:
        mock_stack = mock_stack_cls.return_value
        mock_stack.enter_async_context = AsyncMock(return_value=mock_session)
        mock_stack.aclose = AsyncMock()

        info = await _probe_one_server(
            name="test_server",
            srv_config={"command": "node", "args": ["server.js"]},
            transport="stdio",
        )

        assert info.name == "test_server"
        assert info.status == "ok"
        assert len(info.tools) == 1
        assert info.tools[0].name == "test_tool"
        mock_stack.aclose.assert_called()


@pytest.mark.asyncio
async def test_probe_one_server_task_group_cancellation_unwraps_error():
    """Test that an anyio TaskGroup failure raising CancelledError unwraps the real underlying error upon stack.aclose()."""
    mock_session = AsyncMock()
    # enter_async_context raises CancelledError simulating an anyio TaskGroup background failure
    cancelled_exc = asyncio.CancelledError()

    with patch("opscode.mcp.preload.AsyncExitStack") as mock_stack_cls:
        mock_stack = mock_stack_cls.return_value
        mock_stack.enter_async_context = AsyncMock(side_effect=cancelled_exc)
        # stack.aclose() raises the actual underlying HTTPStatusError / ExceptionGroup
        underlying_error = RuntimeError("401 Unauthorized")
        mock_stack.aclose = AsyncMock(side_effect=underlying_error)

        info = await _probe_one_server(
            name="daloopa",
            srv_config={"url": "https://api.daloopa.com/mcp", "type": "http"},
            transport="http",
        )

        assert info.name == "daloopa"
        assert info.status == "error"
        assert info.error is not None
        assert "401 Unauthorized" in info.error
        mock_stack.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_probe_one_server_re_raises_true_cancellation():
    """Test that true external cancellation (where stack.aclose() doesn't raise an Exception) is re-raised."""
    cancelled_exc = asyncio.CancelledError()

    with patch("opscode.mcp.preload.AsyncExitStack") as mock_stack_cls:
        mock_stack = mock_stack_cls.return_value
        mock_stack.enter_async_context = AsyncMock(side_effect=cancelled_exc)
        mock_stack.aclose = AsyncMock()  # Clean aclose, no underlying error

        with pytest.raises(asyncio.CancelledError):
            await _probe_one_server(
                name="test_server",
                srv_config={"command": "node"},
                transport="stdio",
            )


@pytest.mark.asyncio
async def test_preload_mcp_server_info_no_mcp():
    """Test preload_mcp_server_info with no_mcp=True."""
    result = await preload_mcp_server_info(no_mcp=True)
    assert result == []
