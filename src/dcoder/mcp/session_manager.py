import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List
from mcp import ClientSession
from langchain_mcp_adapters.sessions import (
    SSEConnection,
    StdioConnection,
    StreamableHttpConnection,
    create_session,
)

logger = logging.getLogger("dcoder")

class _MCPSessionEntry:
    def __init__(self, session: ClientSession, exit_stack: AsyncExitStack):
        self.session = session
        self.exit_stack = exit_stack
        self._cached_tools: List[Any] = []

class MCPSessionManager:
    """Manages connections to active MCP servers."""

    def __init__(self, mcp_config: dict[str, Any] | None = None) -> None:
        self._config = mcp_config.get("mcpServers", mcp_config) if mcp_config else {}
        self._sessions: Dict[str, _MCPSessionEntry] = {}
        self._lock = asyncio.Lock()
        # Track connection errors for display in /mcp viewer
        self._errors: Dict[str, str] = {}

    def get_server_status(self) -> list[dict[str, Any]]:
        """Return server status for the ``/mcp`` viewer.

        Returns a list of dicts with keys:
        - name: server name
        - connected: bool
        - status: "ok" | "error" | "disconnected"
        - transport: "stdio" | "sse" | "http"
        - tool_count: int
        - tools: list of tool dicts with name, description, input_schema
        - error: optional error string
        """
        result: list[dict[str, Any]] = []
        for name, config in self._config.items():
            transport = config.get("type") or config.get("transport") or "stdio"
            connected = name in self._sessions
            error = self._errors.get(name)

            tools: list[dict[str, Any]] = []
            if connected:
                try:
                    session = self._sessions[name].session
                    # list_tools is async, but get_server_status is sync.
                    # We'll use cached tools if available, otherwise empty.
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

    async def get_session(self, name: str) -> ClientSession:
        """Get session if exists, otherwise raise KeyError."""
        async with self._lock:
            if name not in self._sessions:
                raise KeyError(f"No active session for MCP server {name}")
            return self._sessions[name].session

    async def list_tools(self, name: str) -> List[Any]:
        """List tools for a given server name."""
        session = await self.get_session(name)
        cursor: str | None = None
        tools = []
        for _ in range(1000):
            page = await session.list_tools(cursor=cursor)
            if page.tools:
                tools.extend(page.tools)
            if not page.nextCursor:
                return tools
            cursor = page.nextCursor
        raise RuntimeError(f"Too many iterations listing tools for {name}")

    async def call_tool(self, name: str, tool_name: str, args: dict[str, Any]) -> Any:
        """Call a tool on the specified server."""
        session = await self.get_session(name)
        return await session.call_tool(tool_name, args)

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
        from langchain_mcp_adapters.tools import convert_mcp_tool_to_langchain_tool
        
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
                for t in tools:
                    l_tool = convert_mcp_tool_to_langchain_tool(session, t)
                    all_tools.append(l_tool)
            except Exception as e:
                self._errors[name] = str(e)
                logger.warning("Failed to connect/load tools for MCP server %s: %s", name, e)
                
        return all_tools
