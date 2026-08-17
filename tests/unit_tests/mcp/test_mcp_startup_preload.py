"""Unit tests verifying non-blocking MCP startup, background concurrency, and session manager resilience."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opscode.mcp.mcp_info import MCPServerInfo
from opscode.mcp.session_manager import MCPSessionManager
from opscode.ui.app import OpsCodeApp


@pytest.mark.asyncio
async def test_app_background_startup_preloads_mcp():
    """Verify that OpsCodeApp._start_server_background runs server start and MCP preload concurrently."""
    app = OpsCodeApp(
        defer_server_start=True,
        server_kwargs={"assistant_id": "opscode"},
        mcp_preload_kwargs={"no_mcp": False, "mcp_config_path": None},
    )

    mock_client = MagicMock()
    mock_server_proc = MagicMock()
    mock_mcp_info = [
        MCPServerInfo(name="test_mcp", transport="stdio", status="ok", tools=())
    ]

    with patch("opscode.cli.server_manager.start_server_and_get_agent", new_callable=AsyncMock) as mock_server_start, \
         patch("opscode.mcp.preload.preload_mcp_server_info", new_callable=AsyncMock) as mock_mcp_preload, \
         patch.object(app, "post_message") as mock_post:

        mock_server_start.return_value = (mock_client, mock_server_proc)
        mock_mcp_preload.return_value = mock_mcp_info

        await app._start_server_background()

        mock_server_start.assert_called_once()
        mock_mcp_preload.assert_called_once()
        mock_post.assert_called_once()

        event = mock_post.call_args[0][0]
        assert isinstance(event, OpsCodeApp.ServerReady)
        assert event.client is mock_client
        assert event.server_proc is mock_server_proc
        assert event.mcp_server_info == mock_mcp_info


@pytest.mark.asyncio
async def test_app_server_ready_updates_mcp_server_info():
    """Verify that OpsCodeApp._on_server_ready updates _mcp_server_info on the app."""
    app = OpsCodeApp(defer_server_start=True)
    assert app._mcp_server_info == []

    mock_mcp_info = [
        MCPServerInfo(name="plugin__aws", transport="stdio", status="ok", tools=())
    ]
    event = OpsCodeApp.ServerReady(
        client=MagicMock(),
        server_proc=MagicMock(),
        mcp_server_info=mock_mcp_info,
    )

    with patch.object(app, "_finalize_connection", new_callable=AsyncMock), \
         patch.object(app, "_process_next_from_queue", new_callable=AsyncMock):
        await app._on_server_ready(event)

    assert app._mcp_server_info == mock_mcp_info


@pytest.mark.asyncio
async def test_session_manager_connect_all_concurrent_with_timeout():
    """Verify that MCPSessionManager.connect_all connects concurrently and isolates slow/failing servers."""
    mcp_config = {
        "mcpServers": {
            "fast_srv": {"command": "node", "args": ["fast.js"]},
            "slow_srv": {"command": "node", "args": ["slow.js"]},
        }
    }
    manager = MCPSessionManager(mcp_config)

    async def mock_connect(name, config):
        if name == "slow_srv":
            await asyncio.sleep(10.0)  # Exceeds 5s timeout
        return MagicMock()

    with patch.object(manager, "connect", side_effect=mock_connect), \
         patch.object(manager, "list_tools", new_callable=AsyncMock, return_value=[]):
        tools = await manager.connect_all(trust_project=True)

        assert isinstance(tools, list)
        assert "slow_srv" in manager._errors
        assert "timed out" in manager._errors["slow_srv"].lower()
