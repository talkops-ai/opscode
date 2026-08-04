"""Schema and middleware for per-checkpoint state restored when resuming.

``ResumeState`` declares several checkpointed, schema-private channels. They
fall into two groups with *different* write paths:

Written from inside the graph on successful model turns:

- ``_context_tokens`` — total context tokens from the latest
    ``AIMessage.usage_metadata``, written by ``ResumeStateMiddleware.after_model``.
- ``_model_spec`` / ``_model_params`` — the model and invocation params
    effectively in use for the turn, written by ``ConfigurableModelMiddleware``.

Written through the main graph or by the TUI client via ``aupdate_state``:

- ``_goal_objective`` / ``_goal_status`` / ``_goal_rubric`` / ``_goal_status_note``
    — the accepted goal and its lifecycle status.
- ``_pending_goal_completion_note`` — optional agent-provided completion
    evidence awaiting the post-turn rubric result.
- ``_sticky_rubric`` — the TUI-owned persistent rubric, distinct from graph
    input ``rubric``.
- ``_pending_goal_objective`` / ``_pending_goal_rubric`` /
    ``_pending_goal_kind`` / ``_pending_goal_request_id`` — a proposed goal or
    amendment and its originating request, written by
    ``GoalCriteriaMiddleware`` inside the main graph, then cleared by the TUI
    when the user accepts or rejects it.
"""

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

GoalStatus = Literal["active", "paused", "blocked", "complete"]
"""Lifecycle status of a TUI-owned goal.

``active`` and ``blocked`` are unfinished working states, ``paused`` preserves
the goal without driving work, and ``complete`` is terminal. A blocked goal is
still considered actionable (``active=True``) by ``get_goal``, whereas a paused
goal is unfinished but reports ``active=False``.
"""

GoalProposalKind = Literal["create", "amend"]
"""Whether a pending review creates a goal or amends the current one."""

_GOAL_STATUS_VALUES: frozenset[str] = frozenset(get_args(GoalStatus))
_GOAL_PROPOSAL_KIND_VALUES: frozenset[str] = frozenset(get_args(GoalProposalKind))


def _flatten_literal_values(tp: object) -> frozenset[str]:
    """Collect every string value from a (possibly unioned) ``Literal`` type.

    Args:
        tp: A ``Literal`` type, or a union of ``Literal``\\ s, to inspect.

    Returns:
        Every string member across the (possibly nested) ``Literal`` args.
    """
    values: set[str] = set()
    for arg in get_args(tp):
        if isinstance(arg, str):
            values.add(arg)
        else:
            values |= _flatten_literal_values(arg)
    return frozenset(values)


try:
    from deepagents.middleware.rubric import RubricResult

    RUBRIC_RESULT_VALUES: frozenset[str] = _flatten_literal_values(RubricResult)
except ImportError:  # pragma: no cover
    RUBRIC_RESULT_VALUES = frozenset({"satisfied", "not_satisfied"})

"""Every verdict ``RubricMiddleware`` can emit for a completed grading run.

Derived from the SDK's ``RubricResult`` ``Literal`` so it cannot drift out of
sync with the grader vocabulary.
"""


def coerce_goal_proposal_kind(value: object) -> GoalProposalKind | None:
    """Narrow a persisted proposal kind to a known value.

    Args:
        value: Raw value read from checkpoint state.

    Returns:
        The recognized proposal kind, otherwise ``None``.
    """
    if isinstance(value, str) and value in _GOAL_PROPOSAL_KIND_VALUES:
        return cast("GoalProposalKind", value)
    return None


def coerce_goal_status(value: object) -> GoalStatus | None:
    """Narrow a persisted goal-status value to a known ``GoalStatus``.

    A corrupt or forward-version checkpoint can carry an unexpected status
    string (or a non-string). Coercing to ``None`` rather than passing the raw
    value through keeps the ``GoalStatus`` ``Literal`` load-bearing on the read
    path, so an unknown status is treated as "no goal status" instead of a
    silently active goal.

    Args:
        value: Raw value read from checkpoint state.

    Returns:
        The value when it is a recognized ``GoalStatus``, otherwise ``None``.
    """
    if isinstance(value, str) and value in _GOAL_STATUS_VALUES:
        return cast("GoalStatus", value)
    return None


class GoalRubricChannels(AgentState):
    """Goal/rubric state channels shared by every schema that touches them.

    Declared once here so each schema that carries these channels —
    ``ResumeState`` and ``goal_tools.GoalToolState`` — inherits the *same*
    ``PrivateStateAttr``-marked annotations. Middleware state schemas merge with
    later entries winning, so an independent re-declaration that dropped the
    ``PrivateStateAttr`` marker would override these and leak the field into the
    public graph input/output schema. Inheriting from a single base makes that
    drift unrepresentable.
    """

    _goal_objective: Annotated[NotRequired[str | None], PrivateStateAttr]
    """Accepted goal objective restored by the TUI on resume."""

    _goal_status: Annotated[NotRequired[GoalStatus | None], PrivateStateAttr]
    """Goal lifecycle status (``active``, ``paused``, ``blocked``, ``complete``, or ``None``)."""

    _goal_rubric: Annotated[NotRequired[str | None], PrivateStateAttr]
    """Accepted rubric associated with ``_goal_objective``."""

    _goal_status_note: Annotated[NotRequired[str | None], PrivateStateAttr]
    """Persisted completion evidence or blocker note for the goal."""

    _pending_goal_completion_note: Annotated[NotRequired[str | None], PrivateStateAttr]
    """Optional agent-provided completion evidence awaiting final grading."""

    _sticky_rubric: Annotated[NotRequired[str | None], PrivateStateAttr]
    """Persistent rubric owned by the TUI, distinct from graph input ``rubric``."""


class ResumeState(GoalRubricChannels):
    """Extends agent state with per-checkpoint facts restored on resume.

    Inherits the shared goal/rubric channels from ``GoalRubricChannels`` and
    adds the channels unique to resume: the after-model token/spec facts and
    the pending-goal proposal awaiting acceptance.
    """

    _context_tokens: Annotated[NotRequired[int], PrivateStateAttr]
    """Total context tokens reported by the model's last ``usage_metadata``."""

    _model_spec: Annotated[NotRequired[str], PrivateStateAttr]
    """``provider:model`` spec effectively in use for the latest turn."""

    _model_params: Annotated[NotRequired[dict[str, Any] | None], PrivateStateAttr]
    """Invocation params effectively in use for the latest turn."""

    _pending_goal_objective: Annotated[NotRequired[str | None], PrivateStateAttr]
    """Goal objective awaiting acceptance of proposed criteria."""

    _pending_goal_rubric: Annotated[NotRequired[str | None], PrivateStateAttr]
    """Proposed criteria awaiting user acceptance."""

    _pending_goal_kind: Annotated[
        NotRequired[GoalProposalKind | None], PrivateStateAttr
    ]
    """Whether the pending review creates or amends a goal."""

    _pending_goal_request_id: Annotated[NotRequired[str | None], PrivateStateAttr]
    """Request that produced the pending proposal."""


def _extract_context_tokens(message: AIMessage) -> int | None:
    """Return the context-token count from an AI message, or ``None`` if absent.

    Prefers ``input_tokens + output_tokens`` when both are reported; falls back
    to ``total_tokens`` when the model only provides the aggregate.
    """
    usage = getattr(message, "usage_metadata", None)
    if not usage:
        return None
    input_toks = usage.get("input_tokens", 0) or 0
    output_toks = usage.get("output_tokens", 0) or 0
    if input_toks or output_toks:
        return input_toks + output_toks
    total = usage.get("total_tokens", 0) or 0
    return total or None


@register_middleware(name="resume_state")
class ResumeStateMiddleware(AgentMiddleware[ResumeState, ContextT]):
    """Persists per-checkpoint resume facts after each model call.

    See the module docstring for why this rides the model node's checkpoint
    instead of a separate ``aupdate_state``.
    """

    state_schema = ResumeState

    def after_model(  # noqa: PLR6301
        self,
        state: ResumeState,
        runtime: Runtime[ContextT],  # noqa: ARG002
    ) -> dict[str, Any] | None:
        """Write ``_context_tokens`` for the latest turn.

        Args:
            state: Current agent state; only ``messages`` is inspected.
            runtime: LangGraph runtime required by the middleware interface.

        Returns:
            State update with ``_context_tokens``, or ``None`` when no token
            count is available.
        """
        update: dict[str, Any] = {}

        for msg in reversed(state.get("messages") or []):
            if isinstance(msg, AIMessage):
                tokens = _extract_context_tokens(msg)
                if tokens is not None:
                    update["_context_tokens"] = tokens
                break

        return update or None
