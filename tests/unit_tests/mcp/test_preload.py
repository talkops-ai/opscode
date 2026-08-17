"""Unit tests for MCP server preloading, remote preflight, concurrency, and error handling."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opscode.mcp.mcp_info import MCPServerInfo, MCPToolInfo
from opscode.mcp.preload import (
    _check_remote_connectivity,
    _probe_one_server,
    preload_mcp_server_info,
)


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
    cancelled_exc = asyncio.CancelledError()

    with patch("opscode.mcp.preload._check_remote_connectivity", return_value=(True, None, "ok")), \
         patch("opscode.mcp.preload.AsyncExitStack") as mock_stack_cls:
        mock_stack = mock_stack_cls.return_value
        mock_stack.enter_async_context = AsyncMock(side_effect=cancelled_exc)
        underlying_error = RuntimeError("401 Unauthorized")
        mock_stack.aclose = AsyncMock(side_effect=underlying_error)

        info = await _probe_one_server(
            name="daloopa",
            srv_config={"url": "https://api.daloopa.com/mcp", "type": "http"},
            transport="http",
        )

        assert info.name == "daloopa"
        assert info.status == "unauthenticated"
        assert info.error is not None
        assert "401 Unauthorized" in info.error
        mock_stack.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_probe_one_server_remote_preflight_unauthenticated():
    """Test that a remote server failing preflight with 401 returns unauthenticated status immediately."""
    with patch("opscode.mcp.preload._check_remote_connectivity", return_value=(False, "HTTP 401 Unauthorized", "unauthenticated")):
        info = await _probe_one_server(
            name="remote_service",
            srv_config={"url": "https://service.example.com/mcp", "type": "http"},
            transport="http",
        )

        assert info.name == "remote_service"
        assert info.status == "unauthenticated"
        assert "401" in (info.error or "")


@pytest.mark.asyncio
async def test_probe_one_server_re_raises_true_cancellation():
    """Test that true external cancellation (where stack.aclose() doesn't raise an Exception) is re-raised."""
    cancelled_exc = asyncio.CancelledError()

    with patch("opscode.mcp.preload.AsyncExitStack") as mock_stack_cls:
        mock_stack = mock_stack_cls.return_value
        mock_stack.enter_async_context = AsyncMock(side_effect=cancelled_exc)
        mock_stack.aclose = AsyncMock()

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


@pytest.mark.asyncio
async def test_preload_mcp_server_info_concurrent():
    """Test preload_mcp_server_info concurrently probes multiple servers."""
    fake_config = {
        "srv1": {"command": "node", "args": ["1.js"]},
        "srv2": {"command": "python", "args": ["2.py"]},
    }

    with patch("opscode.mcp.discovery.MCPDiscovery.discover", return_value=fake_config), \
         patch("opscode.mcp.preload._probe_one_server") as mock_probe:
        mock_probe.side_effect = [
            MCPServerInfo(name="srv1", transport="stdio", status="ok", tools=()),
            MCPServerInfo(name="srv2", transport="stdio", status="ok", tools=()),
        ]

        results = await preload_mcp_server_info()
        assert len(results) == 2
        assert {r.name for r in results} == {"srv1", "srv2"}
        assert mock_probe.call_count == 2
