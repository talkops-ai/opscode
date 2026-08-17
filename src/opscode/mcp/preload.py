"""Preload MCP server metadata for the TUI without keeping sessions alive.

Opens temporary sessions to discover tools, builds :class:`MCPServerInfo`
entries, then **immediately** cleans up. The real MCP sessions used by
the agent are created later inside the server subprocess.

Uses ``create_session`` directly (not ``MCPSessionManager``) to avoid
exit-stack cleanup issues with anyio task groups.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from opscode.mcp.mcp_info import MCPServerInfo, MCPToolInfo

logger = logging.getLogger(__name__)

_REMOTE_PREFLIGHT_TIMEOUT = 2.0
_PROBE_TIMEOUT = 5.0
_MAX_CONCURRENT_PROBES = 8


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


def _is_unauthenticated_error(exc: BaseException) -> bool:
    """Determine whether an exception indicates missing or invalid credentials."""
    msg = str(exc).lower()
    return any(
        kw in msg
        for kw in (
            "401",
            "unauthorized",
            "authentication",
            "unauthenticated",
            "auth required",
            "re-authentication",
            "token refresh failed",
            "forbidden",
            "403",
        )
    )


async def _check_remote_connectivity(url: str) -> tuple[bool, str | None, str]:
    """Fast preflight connectivity check for remote HTTP/SSE servers.

    Returns:
        `(is_ok, error_message, status)`
    """
    if not url:
        return False, "Missing URL in server configuration", "error"
    try:
        import httpx

        async with httpx.AsyncClient(timeout=_REMOTE_PREFLIGHT_TIMEOUT) as client:
            try:
                response = await client.head(url)
            except (httpx.HTTPError, httpx.InvalidURL, OSError):
                response = await client.get(url)

            if response.status_code in (401, 403):
                return False, f"HTTP {response.status_code} Unauthorized - requires token/login", "unauthenticated"
            if response.status_code >= 500:
                return False, f"Server returned HTTP {response.status_code}", "error"
            return True, None, "ok"
    except Exception as exc:
        if _is_unauthenticated_error(exc):
            return False, f"Remote server requires authentication: {exc}", "unauthenticated"
        return False, f"Remote endpoint unreachable: {exc}", "error"


async def _probe_one_server(
    name: str, srv_config: Mapping[str, Any], transport: str
) -> MCPServerInfo:
    """Open a throwaway session to one MCP server and list its tools.

    The session is opened inside an ``AsyncExitStack`` that is closed
    immediately after listing tools. Errors are captured, never raised.
    """
    from langchain_mcp_adapters.sessions import (
        SSEConnection,
        StdioConnection,
        StreamableHttpConnection,
        create_session,
    )

    # Fast remote preflight check
    if transport in ("sse", "http", "streamable_http", "streamable-http"):
        url = str(srv_config.get("url") or "")
        is_ok, preflight_err, preflight_status = await _check_remote_connectivity(url)
        if not is_ok:
            logger.info("MCP preload remote check: %s — %s (%s)", name, preflight_err, preflight_status)
            return MCPServerInfo(
                name=name,
                transport=transport,
                status=preflight_status,  # type: ignore[arg-type]
                error=preflight_err,
            )

    stack = AsyncExitStack()
    try:
        # Build the connection descriptor
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
            url_str: str = srv_config.get("url", "")
            headers: dict[str, Any] | None = srv_config.get("headers")
            connection = SSEConnection(
                transport="sse",
                url=url_str,
                headers=headers,
            )
        elif transport_type in ("http", "streamable_http", "streamable-http"):
            url_str = srv_config.get("url", "")
            headers = srv_config.get("headers")
            connection = StreamableHttpConnection(
                transport="streamable_http",
                url=url_str,
                headers=headers,
            )
        else:
            return MCPServerInfo(
                name=name,
                transport=transport_type,
                status="error",
                error=f"Unknown transport type: {transport_type}",
            )

        async with asyncio.timeout(_PROBE_TIMEOUT):
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

    except TimeoutError:
        try:
            await stack.aclose()
        except Exception:
            pass
        logger.warning("MCP preload: %s timed out after %.1fs", name, _PROBE_TIMEOUT)
        return MCPServerInfo(
            name=name,
            transport=transport,
            status="error",
            error=f"Connection probe timed out after {_PROBE_TIMEOUT}s",
        )
    except BaseException as exc:
        real_exc: BaseException = exc
        try:
            await stack.aclose()
        except Exception as cleanup_exc:
            real_exc = cleanup_exc
        except BaseException as cleanup_base_exc:
            real_exc = cleanup_base_exc

        if isinstance(real_exc, Exception):
            is_unauth = _is_unauthenticated_error(real_exc)
            status_val = "unauthenticated" if is_unauth else "error"
            logger.info("MCP preload: %s status=%s (%s)", name, status_val, real_exc)
            return MCPServerInfo(
                name=name,
                transport=transport,
                status=status_val,  # type: ignore[arg-type]
                error=str(real_exc),
            )
        raise real_exc


async def preload_mcp_server_info(
    *,
    mcp_config_path: str | None = None,
    no_mcp: bool = False,
    trust_project_mcp: bool | None = None,
) -> list[MCPServerInfo]:
    """Discover MCP servers, open temporary sessions to list tools, then close.

    Runs concurrently in background and returns metadata for the
    ``/mcp`` viewer. Sessions are ephemeral — opened only to capture
    tool metadata, then immediately closed.

    Args:
        mcp_config_path: Optional explicit path to an MCP config JSON.
        no_mcp: When ``True``, skip all MCP loading.
        trust_project_mcp: Optional whole-config trust override.

    Returns:
        List of :class:`MCPServerInfo` entries for every discovered server.
    """
    if no_mcp:
        return []

    # 1. Discover configs via standard paths (including plugins and project configs)
    from opscode.mcp.discovery import MCPDiscovery

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

    # 3. Probe servers concurrently with bounded concurrency
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_PROBES)

    async def _bounded_probe(server_name: str, srv_cfg: Mapping[str, Any]) -> MCPServerInfo:
        async with semaphore:
            transport_type = _resolve_transport(srv_cfg)
            return await _probe_one_server(server_name, srv_cfg, transport_type)

    tasks = [
        _bounded_probe(name, srv_config)
        for name, srv_config in config.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    server_infos: list[MCPServerInfo] = []
    for (name, srv_config), res in zip(config.items(), results):
        if isinstance(res, MCPServerInfo):
            server_infos.append(res)
        elif isinstance(res, Exception):
            server_infos.append(
                MCPServerInfo(
                    name=name,
                    transport=_resolve_transport(srv_config),
                    status="error",
                    error=str(res),
                )
            )

    return server_infos


__all__ = ["preload_mcp_server_info"]
