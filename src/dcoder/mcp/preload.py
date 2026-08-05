"""Preload MCP server metadata for the TUI without keeping sessions alive.

Replicates dcode's ``_preload_session_mcp_server_info`` pattern: open
temporary sessions to discover tools, build :class:`MCPServerInfo`
entries, then **immediately** clean up.  The real MCP sessions used by
the agent are created later inside the server subprocess.

Uses ``create_session`` directly (not ``MCPSessionManager``) to avoid
exit-stack cleanup issues with anyio task groups.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import AsyncExitStack
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from dcoder.mcp.mcp_info import MCPServerInfo, MCPToolInfo

logger = logging.getLogger(__name__)


def _resolve_transport(config: Mapping[str, Any]) -> str:
    """Determine the transport type from a server config dict."""
    transport = config.get("type") or config.get("transport")
    if transport:
        return str(transport)
    url = config.get("url", "")
    if url:
        if "sse" in str(url).lower():
            return "sse"
        return "http"
    return "stdio"


async def _probe_one_server(
    name: str, srv_config: Mapping[str, Any], transport: str
) -> MCPServerInfo:
    """Open a throwaway session to one MCP server and list its tools.

    The session is opened inside an ``AsyncExitStack`` that is closed
    immediately after listing tools.  Errors are captured, never raised.
    """
    from langchain_mcp_adapters.sessions import (
        SSEConnection,
        StdioConnection,
        StreamableHttpConnection,
        create_session,
    )

    stack = AsyncExitStack()
    try:
        # Build the connection descriptor (TypedDicts require `transport` key)
        connection: StdioConnection | SSEConnection | StreamableHttpConnection
        transport_type = transport
        if transport_type == "stdio":
            command: str = srv_config.get("command", "")
            args: list[str] = srv_config.get("args", [])
            env: dict[str, str] | None = srv_config.get("env")
            connection = StdioConnection(
                transport="stdio",
                command=command,
                args=args,
                env=env,
            )
        elif transport_type == "sse":
            url: str = srv_config.get("url", "")
            headers: dict[str, Any] | None = srv_config.get("headers")
            connection = SSEConnection(
                transport="sse",
                url=url,
                headers=headers,
            )
        elif transport_type in ("http", "streamable_http", "streamable-http"):
            url = srv_config.get("url", "")
            headers = srv_config.get("headers")
            connection = StreamableHttpConnection(
                transport="streamable_http",
                url=url,
                headers=headers,
            )
        else:
            return MCPServerInfo(
                name=name,
                transport=transport_type,
                status="error",
                error=f"Unknown transport type: {transport_type}",
            )

        # Open session, initialize if needed, list tools, and close immediately
        session = await stack.enter_async_context(create_session(connection))
        if hasattr(session, "initialize"):
            await session.initialize()
        resp = await session.list_tools()
        raw_tools: Any = getattr(resp, "tools", resp)

        tool_infos = tuple(
            MCPToolInfo(
                name=getattr(t, "name", str(t)),
                description=getattr(t, "description", ""),
                input_schema=getattr(t, "inputSchema", None),
            )
            for t in raw_tools
        )

        logger.info("MCP preload: %s — %d tools discovered", name, len(tool_infos))

        await stack.aclose()

        return MCPServerInfo(
            name=name,
            transport=transport_type,
            tools=tool_infos,
            status="ok",
        )

    except BaseException as exc:
        # A background task failure in anyio TaskGroup (e.g. HTTP 401 Unauthorized) enters
        # cancel scope, causing asyncio.CancelledError on the main task.
        # Calling stack.aclose() in *this* task will exit the cancel scope in the same task
        # that entered it. stack.aclose() finalization raises the actual underlying exception
        # (e.g. ExceptionGroup containing HTTP 401).
        real_exc: BaseException = exc
        try:
            await stack.aclose()
        except Exception as cleanup_exc:
            real_exc = cleanup_exc
        except BaseException as cleanup_base_exc:
            real_exc = cleanup_base_exc

        if isinstance(real_exc, Exception):
            logger.warning("MCP preload: %s failed — %s", name, real_exc)
            return MCPServerInfo(
                name=name,
                transport=transport,
                status="error",
                error=str(real_exc),
            )
        raise real_exc


async def preload_mcp_server_info(
    *,
    mcp_config_path: str | None = None,
    no_mcp: bool = False,
) -> list[MCPServerInfo]:
    """Discover MCP servers, open temp sessions to list tools, then close.

    This runs **before** the TUI app starts and returns metadata for the
    ``/mcp`` viewer.  Sessions are ephemeral — opened only to capture
    tool metadata, then immediately closed.

    Args:
        mcp_config_path: Optional explicit path to an MCP config JSON.
        no_mcp: When ``True``, skip all MCP loading.

    Returns:
        List of :class:`MCPServerInfo` entries for every discovered server.
        Failed servers appear with ``status='error'`` and their error message.
    """
    if no_mcp:
        return []

    # 1. Discover configs via standard paths
    from dcoder.mcp.discovery import MCPDiscovery

    discovery = MCPDiscovery()
    config: dict[str, Any] = dict(discovery.discover())

    # 2. If explicit config path provided, merge it in (highest precedence)
    if mcp_config_path:
        try:
            path = Path(mcp_config_path)
            if path.is_file():
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                servers = data.get("mcpServers")
                if isinstance(servers, dict):
                    for name, srv_config in servers.items():
                        if isinstance(srv_config, dict):
                            config[name] = srv_config
        except Exception as e:
            logger.warning(
                "Failed to load explicit MCP config %s: %s", mcp_config_path, e
            )

    if not config:
        return []

    # 3. Probe each server independently
    server_infos: list[MCPServerInfo] = []
    for name, srv_config in config.items():
        transport = _resolve_transport(srv_config)
        info = await _probe_one_server(name, srv_config, transport)
        server_infos.append(info)

    return server_infos


__all__ = ["preload_mcp_server_info"]
