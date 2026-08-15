import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, Awaitable, Callable, Dict, List
from mcp import ClientSession
from langchain_mcp_adapters.sessions import (
    SSEConnection,
    StdioConnection,
    StreamableHttpConnection,
    create_session,
)

logger = logging.getLogger("opscode")

class _MCPSessionEntry:
    def __init__(self, session: ClientSession, exit_stack: AsyncExitStack):
        self.session = session
        self.exit_stack = exit_stack
        self._cached_tools: List[Any] = []

def _is_transient_session_error(exc: BaseException) -> bool:
    """Return True when exc signals the MCP session transport or stream is dead."""
    try:
        import anyio
        anyio_excs = (
            anyio.ClosedResourceError,
            anyio.BrokenResourceError,
            anyio.EndOfStream,
        )
    except ImportError:
        anyio_excs = ()
    return isinstance(
        exc,
        (
            *anyio_excs,
            BrokenPipeError,
            ConnectionAbortedError,
            ConnectionResetError,
            EOFError,
            asyncio.IncompleteReadError,
        ),
    )


def _normalize_mcp_arguments(arguments: dict[str, Any], input_schema: Any) -> dict[str, Any]:
    """Normalize MCP tool arguments, stripping empty string values for non-required fields."""
    if not isinstance(input_schema, dict):
        return arguments
    required = set(input_schema.get("required") or ())
    properties = input_schema.get("properties") or {}
    cleaned: dict[str, Any] = {}
    for key, value in arguments.items():
        if value != "" or key in required:
            cleaned[key] = value
            continue
        prop = properties.get(key)
        prop_type = prop.get("type") if isinstance(prop, dict) else None
        is_string_typed = prop_type == "string" or (
            isinstance(prop_type, list) and "string" in prop_type
        )
        if isinstance(prop, dict) and not is_string_typed and prop_type is not None:
            cleaned[key] = value
    return cleaned


class MCPSessionManager:
    """Manages connections to active MCP servers."""

    def __init__(self, mcp_config: dict[str, Any] | None = None) -> None:
        self._config = mcp_config.get("mcpServers", mcp_config) if mcp_config else {}
        self._sessions: Dict[str, _MCPSessionEntry] = {}
        self._lock = asyncio.Lock()
        # Track connection errors for display in /mcp viewer
        self._errors: Dict[str, str] = {}

    def get_server_status(self) -> list[dict[str, Any]]:
        """Return server status for the ``/mcp`` viewer."""
        result: list[dict[str, Any]] = []
        for name, config in self._config.items():
            transport = config.get("type") or config.get("transport") or "stdio"
            connected = name in self._sessions
            error = self._errors.get(name)

            tools: list[dict[str, Any]] = []
            if connected:
                try:
                    cached = getattr(self._sessions[name], "_cached_tools", None)
                    if cached:
                        for t in cached:
                            tools.append({
                                "name": getattr(t, "name", str(t)),
                                "description": getattr(t, "description", ""),
                                "input_schema": getattr(t, "inputSchema", None),
                            })
                except Exception:
                    pass

            status = "ok" if connected else ("error" if error else "disconnected")
            result.append({
                "name": name,
                "connected": connected,
                "status": status,
                "transport": transport,
                "tool_count": len(tools),
                "tools": tools,
                "error": error,
            })
        return result

    async def connect(self, name: str, config: dict[str, Any]) -> ClientSession:
        """Connect to an MCP server lazily, caching the session."""
        async with self._lock:
            if name in self._sessions:
                return self._sessions[name].session

            # Resolve transport
            transport = config.get("type") or config.get("transport")
            url = str(config.get("url") or "")
            
            if transport == "http" or (not transport and url and "http" in url):
                conn = StreamableHttpConnection(
                    transport="streamable_http",
                    url=url,
                    headers=config.get("headers"),
                )
            elif transport == "sse" or (not transport and url and "sse" in url):
                conn = SSEConnection(
                    transport="sse",
                    url=url,
                    headers=config.get("headers"),
                )
            else:
                conn = StdioConnection(
                    command=config.get("command", ""),
                    args=config.get("args") or [],
                    env=config.get("env"),
                    transport="stdio",
                )

            exit_stack = AsyncExitStack()
            try:
                session = await exit_stack.enter_async_context(create_session(conn))
                await session.initialize()
                self._sessions[name] = _MCPSessionEntry(session=session, exit_stack=exit_stack)
                return session
            except BaseException:
                try:
                    await exit_stack.aclose()
                except Exception as cleanup_exc:
                    logger.warning("Failed to close partially initialized MCP session for %s: %s", name, cleanup_exc)
                raise

    async def invalidate(
        self, name: str, expected_session: ClientSession | None = None
    ) -> None:
        """Evict and close a cached session if it matches expected_session."""
        async with self._lock:
            entry = self._sessions.get(name)
            if entry is None:
                return
            if expected_session is not None and entry.session is not expected_session:
                return
            self._sessions.pop(name, None)
            exit_stack = entry.exit_stack

        try:
            await exit_stack.aclose()
        except Exception as e:
            logger.warning("Failed to close invalidated MCP session for %s: %s", name, e)

    async def get_session(self, name: str) -> ClientSession:
        """Get cached session, or lazily connect if configured."""
        async with self._lock:
            if name in self._sessions:
                return self._sessions[name].session

        if name in self._config:
            return await self.connect(name, self._config[name])

        raise KeyError(f"No configuration or active session for MCP server '{name}'")

    async def list_tools(self, name: str) -> List[Any]:
        """List tools for a given server name."""
        session = await self.get_session(name)
        cursor: str | None = None
        tools = []
        for _ in range(1000):
            if cursor:
                from mcp.types import PaginatedRequestParams
                page = await session.list_tools(params=PaginatedRequestParams(cursor=cursor))
            else:
                page = await session.list_tools()
            if page.tools:
                tools.extend(page.tools)
            if not page.nextCursor:
                return tools
            cursor = page.nextCursor
        raise RuntimeError(f"Too many iterations listing tools for {name}")

    async def call_tool(self, name: str, tool_name: str, args: dict[str, Any]) -> Any:
        """Call a tool on the specified server with automatic reconnect on transient stream error."""
        session = await self.get_session(name)
        try:
            return await session.call_tool(tool_name, args)
        except Exception as exc:
            if not _is_transient_session_error(exc):
                raise
            logger.info(
                "MCP session for %r appears dead (%s: %s); invalidating and retrying once",
                name,
                type(exc).__name__,
                exc,
            )
            await self.invalidate(name, expected_session=session)
            retry_session = await self.get_session(name)
            return await retry_session.call_tool(tool_name, args)

    async def disconnect(self, name: str) -> None:
        """Disconnect a specific server session."""
        async with self._lock:
            entry = self._sessions.pop(name, None)
            if entry:
                await entry.exit_stack.aclose()

    async def disconnect_all(self) -> None:
        """Disconnect all active servers."""
        async with self._lock:
            names = list(self._sessions.keys())
            for name in names:
                entry = self._sessions.pop(name, None)
                if entry:
                    try:
                        await entry.exit_stack.aclose()
                    except Exception as e:
                        logger.warning("Error closing MCP session for %s: %s", name, e)

    async def connect_all(self, trust_project: bool = True) -> list[Any]:
        """Connect to all configured servers and return converted LangChain tools."""
        all_tools = []
        for name, config in self._config.items():
            is_stdio = (config.get("type") or config.get("transport") or "stdio") == "stdio"
            is_project_level = config.get("source") == "project"
            if is_stdio and is_project_level and not trust_project:
                logger.warning("Skipping untrusted project stdio MCP server: %s", name)
                continue
                
            try:
                session = await self.connect(name, config)
                tools = await self.list_tools(name)
                # Cache tools on the session entry for sync get_server_status
                if name in self._sessions:
                    self._sessions[name]._cached_tools = tools
                self._errors.pop(name, None)  # Clear any previous error

                from langchain_core.tools import StructuredTool

                for t in tools:
                    t_name = getattr(t, "name", str(t))
                    raw_schema = getattr(t, "inputSchema", None)
                    t_schema: dict[str, Any] = raw_schema if isinstance(raw_schema, dict) else {}

                    def _make_tool_coro(srv_name: str, raw_tool_name: str, schema: Any) -> Callable[..., Awaitable[Any]]:
                        async def _coro(runtime: Any = None, **arguments: Any) -> Any:
                            cleaned = _normalize_mcp_arguments(arguments, schema)
                            return await self.call_tool(srv_name, raw_tool_name, cleaned)
                        return _coro

                    l_tool = StructuredTool(
                        name=t_name,
                        description=getattr(t, "description", "") or "",
                        args_schema=t_schema,
                        coroutine=_make_tool_coro(name, t_name, t_schema),
                    )
                    all_tools.append(l_tool)
            except Exception as e:
                self._errors[name] = str(e)
                logger.warning("Failed to connect/load tools for MCP server %s: %s", name, e)
                
        return all_tools
