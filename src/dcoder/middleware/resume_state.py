from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    NotRequired,
    cast,
    get_args,
)

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    PrivateStateAttr,
)
from langchain_core.messages import AIMessage
from dcoder.middleware.registry import register_middleware

if TYPE_CHECKING:
    from langgraph.runtime import Runtime

GoalStatus = Literal["active", "blocked", "complete"]

_GOAL_STATUS_VALUES: frozenset[str] = frozenset(get_args(GoalStatus))


def coerce_goal_status(value: object) -> GoalStatus | None:
    if isinstance(value, str) and value in _GOAL_STATUS_VALUES:
        return cast("GoalStatus", value)
    return None


class GoalRubricChannels(AgentState):
    _goal_objective: Annotated[NotRequired[str | None], PrivateStateAttr]
    _goal_status: Annotated[NotRequired[GoalStatus | None], PrivateStateAttr]
    _goal_rubric: Annotated[NotRequired[str | None], PrivateStateAttr]
    _goal_status_note: Annotated[NotRequired[str | None], PrivateStateAttr]
    _pending_goal_completion_note: Annotated[NotRequired[str | None], PrivateStateAttr]
    _sticky_rubric: Annotated[NotRequired[str | None], PrivateStateAttr]


class ResumeState(GoalRubricChannels):
    _context_tokens: Annotated[NotRequired[int], PrivateStateAttr]
    _model_spec: Annotated[NotRequired[str], PrivateStateAttr]
    _model_params: Annotated[NotRequired[dict[str, Any] | None], PrivateStateAttr]
    _pending_goal_objective: Annotated[NotRequired[str | None], PrivateStateAttr]
    _pending_goal_rubric: Annotated[NotRequired[str | None], PrivateStateAttr]


def _extract_context_tokens(message: AIMessage) -> int | None:
    usage = getattr(message, "usage_metadata", None)
    if not usage:
        return None
    input_toks = usage.get("input_tokens", 0) or 0
    output_toks = usage.get("output_tokens", 0) or 0
    if input_toks or output_toks:
        return input_toks + output_toks
    total = usage.get("total_tokens", 0) or 0
    return total or None


@register_middleware(name="resume_state", order=20)
class ResumeStateMiddleware(AgentMiddleware[ResumeState, ContextT]):
    state_schema = ResumeState

    def after_model(
        self,
        state: ResumeState,
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        update: dict[str, Any] = {}

        for msg in reversed(state.get("messages") or []):
            if isinstance(msg, AIMessage):
                tokens = _extract_context_tokens(msg)
                if tokens is not None:
                    update["_context_tokens"] = tokens
                break

        return update or None
