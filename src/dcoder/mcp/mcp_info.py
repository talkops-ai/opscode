"""MCP server and tool metadata for display in the TUI.

These frozen dataclasses carry the information the ``/mcp`` viewer needs
without coupling the TUI process to live MCP sessions.  They are built
once by :func:`dcoder.mcp.preload.preload_mcp_server_info` at
startup and passed through ``DCoderApp.__init__``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


MCPServerStatus = Literal[
    "ok",
    "unauthenticated",
    "error",
    "disabled",
    "disconnected",
]
"""Load states a configured MCP server can end up in.

``ok`` — server loaded successfully and has an authoritative tool list.
``unauthenticated`` — server requires OAuth login before tools can load.
``error`` — server failed to load after a connection/config failure.
``disabled`` — user turned the server off via the TUI (``/mcp`` → F2).
``disconnected`` — server is configured but not yet connected.
"""


@dataclass(frozen=True, slots=True)
class MCPToolInfo:
    """Metadata for a single tool exposed by an MCP server."""

    name: str
    """Tool name as registered by the MCP server."""

    description: str = ""
    """Human-readable description of what the tool does."""

    input_schema: dict[str, Any] | None = None
    """Raw MCP ``inputSchema`` dict (JSON Schema), or ``None``."""


@dataclass(frozen=True)
class MCPServerInfo:
    """Metadata for a configured MCP server and its tools.

    Adapted from dcode's ``MCPServerInfo`` dataclass.
    """

    name: str
    """Server name from the MCP configuration."""

    transport: str = "stdio"
    """Transport identifier — ``stdio``, ``sse``, or ``http``."""

    tools: tuple[MCPToolInfo, ...] = ()
    """Tools exposed by this server (empty when ``status != 'ok'``)."""

    status: MCPServerStatus = "ok"
    """Load status."""

    error: str | None = None
    """Human-readable reason when ``status != 'ok'``."""

    @property
    def connected(self) -> bool:
        """Whether the server loaded successfully."""
        return self.status == "ok"

    @property
    def tool_count(self) -> int:
        """Number of tools available on this server."""
        return len(self.tools)

    def needs_attention(self) -> bool:
        """Return whether this server is blocked on user login."""
        return self.status == "unauthenticated"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for backward compatibility."""
        return {
            "name": self.name,
            "connected": self.connected,
            "status": self.status,
            "transport": self.transport,
            "tool_count": self.tool_count,
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in self.tools
            ],
            "error": self.error,
        }


__all__ = ["MCPServerInfo", "MCPServerStatus", "MCPToolInfo"]
