import logging
from typing import Any, Callable, Awaitable
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from dcoder.middleware.registry import register_middleware
from dcoder.mcp.session_manager import MCPSessionManager

logger = logging.getLogger("dcoder")

_TOOL_NAME_DISPLAY_LIMIT = 10
_MCP_ERROR_DETAIL_LIMIT = 200

def _sanitize_error_detail(error: str | None) -> str:
    if not error:
        return "unknown error"
    from dcoder.security.unicode_security import sanitize_control_chars
    sanitized = sanitize_control_chars(error, max_length=_MCP_ERROR_DETAIL_LIMIT)
    return sanitized or "unknown error"

@register_middleware(name="mcp", order=30)
class MCPContextMiddleware(AgentMiddleware):
    """Inject MCP server inventory into the system prompt."""

    def __init__(self, session_manager: MCPSessionManager | None = None, mcp_config: dict | None = None) -> None:
        super().__init__()
        self._manager = session_manager
        self._config = mcp_config or {}

    def _build_mcp_context(self) -> str:
        """Format MCP server/tool inventory for the system prompt."""
        if not self._config:
            return ""

        lines = ["**MCP Servers**:"]
        for name, cfg in self._config.items():
            transport = cfg.get("type") or cfg.get("transport") or "stdio"
            if self._manager and name in self._manager._sessions:
                lines.append(f"- **{name}** ({transport}): connected")
            else:
                lines.append(f"- **{name}** ({transport}): configured (lazy-loaded)")

        return "\n".join(lines)

    def _get_modified_request(self, request: ModelRequest) -> ModelRequest:
        mcp_context = self._build_mcp_context()
        if not mcp_context:
            return request
        from langchain_core.messages import SystemMessage
        existing = request.system_message
        existing_text = existing.content if existing else ""
        new_text = str(existing_text) + "\n\n" + mcp_context
        return request.override(system_message=SystemMessage(content=new_text))

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        modified_request = self._get_modified_request(request)
        return handler(modified_request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        modified_request = self._get_modified_request(request)
        return await handler(modified_request)
