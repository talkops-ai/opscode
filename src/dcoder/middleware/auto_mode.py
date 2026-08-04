"""Classifier-backed approval policy middleware for the local interactive runtime."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.human_in_the_loop import (
    HumanInTheLoopMiddleware,
    InterruptOnConfig,
)
from langchain.agents.middleware.types import (
    AgentState,
    ExtendedModelResponse,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
)
import uuid

USER_PROMPT_METADATA_KEY = "deepagents_code_user_prompt"


def user_prompt_metadata(
    literal_user_text: str,
    referenced_paths: list[str] | None = None,
    turn_id: str | None = None,
) -> dict[str, Any]:
    return {
        "literal_user_text": literal_user_text,
        "referenced_paths": list(referenced_paths or []),
        "turn_id": turn_id or str(uuid.uuid4()),
    }


from langchain_core.messages import AIMessage
from langgraph.types import Command
from dcoder.middleware.registry import register_middleware

logger = logging.getLogger("dcoder")


@register_middleware(name="auto_mode_hitl")
class AutoModeHITLMiddleware(HumanInTheLoopMiddleware[AgentState[Any], Any, Any]):
    """Classifier-backed approval policy middleware for dynamic tool call decisions."""

    def __init__(
        self,
        interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
        *,
        worktree_root: Any | None = None,
        shell_allow_list: list[str] | None = None,
    ) -> None:
        super().__init__(interrupt_on or {})
        self._worktree_root = worktree_root
        self._shell_allow_list = shell_allow_list or []

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any] | ExtendedModelResponse[Any]:
        response = await handler(request)
        ai_message = next(
            (
                message
                for message in reversed(response.result)
                if isinstance(message, AIMessage)
            ),
            None,
        )
        if ai_message is None or not getattr(ai_message, "tool_calls", None):
            return ExtendedModelResponse(
                model_response=response,
                command=Command(update={"_auto_decision_plan": None}),
            )

        calls = list(getattr(ai_message, "tool_calls", []))
        gated_calls = [call for call in calls if call["name"] in self.interrupt_on]
        if not gated_calls:
            return response

        return ExtendedModelResponse(
            model_response=response,
            command=Command(
                update={
                    "_auto_decision_plan": {
                        "batch_id": f"batch-{len(calls)}",
                        "gated_calls_count": len(gated_calls),
                    }
                }
            ),
        )
