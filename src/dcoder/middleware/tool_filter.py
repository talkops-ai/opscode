"""Tool filtering proxy middleware for restricting subagent tool access."""

from __future__ import annotations

import fnmatch
import logging
from typing import Any, Callable, Sequence
from langchain.agents.middleware.types import AgentMiddleware, ToolCallRequest
from langchain_core.messages import ToolMessage
from dcoder.middleware.registry import register_middleware

logger = logging.getLogger("dcoder")


@register_middleware(name="tool_filter")
class ToolFilterMiddleware(AgentMiddleware):
    """Filters tool calls against a whitelist of allowed tool patterns (fnmatch format)."""

    def __init__(self, allowed_patterns: Sequence[str] | None = None) -> None:
        super().__init__()
        self._allowed_patterns = tuple(allowed_patterns) if allowed_patterns is not None else ()

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool name matches any of the allowed patterns."""
        if not self._allowed_patterns:
            return True
        for pattern in self._allowed_patterns:
            if fnmatch.fnmatch(tool_name, pattern) or fnmatch.fnmatch(tool_name.lower(), pattern.lower()):
                return True
        return False

    def _validate_tool_call(self, request: ToolCallRequest) -> ToolMessage | None:
        tool_name = request.tool_call.get("name", "")
        if self.is_tool_allowed(tool_name):
            return None

        logger.warning("Tool call %r blocked for subagent (not in allowed list: %s)", tool_name, self._allowed_patterns)
        allowed_str = ", ".join(self._allowed_patterns)
        return ToolMessage(
            content=(
                f"Tool call rejected: tool `{tool_name}` is restricted for this subagent. "
                f"Allowed tool patterns: [{allowed_str}]."
            ),
            name=tool_name,
            tool_call_id=request.tool_call.get("id", ""),
            status="error",
        )

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ) -> Any:
        err = self._validate_tool_call(request)
        if err is not None:
            return err
        try:
            return handler(request)
        except TypeError as e:
            import traceback
            logger.error("CRITICAL TYPE ERROR on tool call: %s", request)
            logger.error("Traceback: %s", "".join(traceback.format_exception(type(e), e, e.__traceback__)))
            raise

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ) -> Any:
        err = self._validate_tool_call(request)
        if err is not None:
            return err
        try:
            return await handler(request)
        except TypeError as e:
            import traceback
            logger.error("CRITICAL TYPE ERROR on async tool call: %s", request)
            logger.error("Traceback: %s", "".join(traceback.format_exception(type(e), e, e.__traceback__)))
            raise
