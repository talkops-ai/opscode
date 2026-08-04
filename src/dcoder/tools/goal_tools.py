"""Goal management tools exposed to the agent for persisted TUI goals.

These tools let the model inspect and update the TUI-owned goal lifecycle.
They operate on checkpointed ``PrivateStateAttr`` channels shared between the
``GoalToolsMiddleware`` (which registers them) and ``ResumeState`` (which
declares the channels).

The tools are intentionally constrained:

- ``get_goal`` / ``get_rubric`` are read-only projections.
- ``update_goal`` can only mark a goal ``complete`` or ``blocked``; creation,
  pausing, resuming, and clearing are user-controlled TUI actions.
- Completion is **staged** via ``_pending_goal_completion_note`` rather than
  committed directly, so ``RubricMiddleware`` can verify acceptance criteria
  before the TUI records the status change.
"""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    NotRequired,
    TypedDict,
)

from langchain.agents.middleware.types import AgentState, PrivateStateAttr
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import Field

from dcoder.middleware.resume_state import (
    GoalRubricChannels,
    GoalStatus,
    coerce_goal_status,
)

if TYPE_CHECKING:
    pass

GOAL_TOOL_NAMES = frozenset({"get_goal", "get_rubric", "update_goal"})
"""Tool names used by behavioral absence gates and middleware contract tests."""


# ---------------------------------------------------------------------------
# State projection used by tools
# ---------------------------------------------------------------------------


class GoalToolState(GoalRubricChannels):
    """State fields used by goal tools.

    Inherits the shared ``_goal_*``/``_sticky_rubric`` channels (with their
    ``PrivateStateAttr`` markers) from ``GoalRubricChannels``, so the goal tools
    and ``ResumeState`` cannot drift apart. Adds only the public ``rubric``
    graph input, which is intentionally non-private — it is the
    ``RubricMiddleware`` input.
    """

    rubric: NotRequired[str | None]
    """Public ``RubricMiddleware`` graph input (intentionally non-private).

    Distinct from the TUI-owned ``_sticky_rubric``: this is the per-invocation
    rubric passed in via the graph schema, not checkpointed TUI state.
    """


# ---------------------------------------------------------------------------
# Snapshot types
# ---------------------------------------------------------------------------


class RubricSnapshot(TypedDict):
    """Read-only rubric view returned by the ``get_rubric`` tool to the model.

    ``active`` is always ``criteria is not None``; the two never disagree.
    """

    active: bool
    """Whether acceptance criteria are currently available."""

    criteria: str | None
    """Current acceptance criteria, or ``None`` when no rubric is set."""

    grading_status: str | None
    """Latest ``RubricMiddleware`` grading status for the in-progress or
    just-completed graded turn, or ``None``.

    The middleware clears this at the start of the next graded turn, so
    a ``None`` does not imply grading never ran.
    """


class GoalSnapshot(TypedDict):
    """Read-only goal view returned by the ``get_goal`` tool to the model.

    A fixed-shape projection of goal state. Both construction branches in
    ``_goal_snapshot`` must populate every key, so the type checker catches a
    drift between them.
    """

    active: bool
    """Whether the goal is actionable (should drive work).

    Derived from ``status``: ``active`` and ``blocked`` goals are actionable,
    while ``paused`` and ``complete`` goals are not. Note a ``paused`` goal is
    unfinished yet reports ``active=False``. ``False`` when no goal is set (the
    ``objective is None`` branch), where ``status`` is also ``None``.
    """

    objective: str | None
    """Active goal objective, or ``None`` when no goal is set."""

    status: GoalStatus | None
    """Lifecycle status, or ``None`` when no goal is set.

    A set-but-unlabeled or unrecognized persisted value is normalized to
    ``"active"`` by ``coerce_goal_status``, so this is always a known
    ``GoalStatus`` when a goal is set.
    """

    criteria: str | None
    """Persisted goal criteria, or shared rubric criteria when no goal rubric
    exists."""

    note: str | None
    """Persisted completion evidence or blocker note for the goal."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_state_text(state: dict[str, Any], key: str) -> str | None:
    """Return a non-empty stripped string from ``state[key]``, or ``None``.

    Used by snapshot builders to normalize empty strings and whitespace-only
    values to ``None`` so the model sees a clean signal.
    """
    value = state.get(key)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


# ---------------------------------------------------------------------------
# Snapshot builders
# ---------------------------------------------------------------------------


def _rubric_snapshot(state: dict[str, Any]) -> RubricSnapshot:
    """Build the ``get_rubric`` response from graph state.

    Criteria resolve in precedence order: public ``rubric`` input, else an
    actionable goal rubric, else a standalone sticky rubric. Goal lifecycle
    and sticky ownership stay in app state logic; this tool only exposes the
    current criteria and grading status.

    Args:
        state: Current graph state injected by LangGraph.

    Returns:
        Rubric snapshot visible to the model.
    """
    criteria = _clean_state_text(state, "rubric")
    goal_rubric = _clean_state_text(state, "_goal_rubric")
    sticky_rubric = _clean_state_text(state, "_sticky_rubric")
    objective = _clean_state_text(state, "_goal_objective")
    status = coerce_goal_status(state.get("_goal_status")) or "active"
    goal_is_actionable = objective is not None and status in {"active", "blocked"}
    sticky_is_goal_rubric = objective is not None and sticky_rubric == goal_rubric

    # Prefer the public `rubric` graph input when present; otherwise surface
    # actionable goal criteria or a standalone sticky rubric.
    if criteria is None:
        if goal_is_actionable and goal_rubric is not None:
            criteria = goal_rubric
        elif sticky_rubric is not None and not sticky_is_goal_rubric:
            criteria = sticky_rubric

    # ``_rubric_status`` is owned by the SDK's ``RubricMiddleware``, co-composed
    # into this agent's graph.
    grading_status = _clean_state_text(state, "_rubric_status")
    return {
        "active": criteria is not None,
        "criteria": criteria,
        "grading_status": grading_status,
    }


def _goal_snapshot(state: dict[str, Any]) -> GoalSnapshot:
    """Build the ``get_goal`` response from graph state.

    Args:
        state: Current graph state injected by LangGraph.

    Returns:
        Goal snapshot visible to the model.
    """
    objective = _clean_state_text(state, "_goal_objective")
    rubric = _rubric_snapshot(state)
    if objective is None:
        return {
            "active": False,
            "objective": None,
            "status": None,
            "criteria": rubric["criteria"],
            "note": None,
        }
    # A set-but-unlabeled or unrecognized status defaults to "active"; an
    # unknown persisted value never leaks to the model as a bogus status.
    status: GoalStatus = coerce_goal_status(state.get("_goal_status")) or "active"
    criteria = _clean_state_text(state, "_goal_rubric") or rubric["criteria"]
    note = _clean_state_text(state, "_goal_status_note")
    return {
        # Blocked goals remain actionable, while paused and complete goals do
        # not drive work until the user changes their state.
        "active": status in {"active", "blocked"},
        "objective": objective,
        "status": status,
        "criteria": criteria,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Update command builder
# ---------------------------------------------------------------------------


def _update_goal_command(
    *,
    status: Literal["complete", "blocked"],
    note: str,
    tool_call_id: str,
    state: dict[str, Any],
) -> Command[Any]:
    """Build the constrained ``update_goal`` command.

    Args:
        status: Goal status the model is reporting (``complete`` or ``blocked``).
        note: Evidence the goal is complete, or the specific blocker. Required;
            the status is not committed without it.
        tool_call_id: Tool call ID for the returned ``ToolMessage``.
        state: Current graph state injected by LangGraph.

    Returns:
        Command updating goal metadata and returning a tool response.
        A ``complete`` request stages ``_pending_goal_completion_note`` for
        the TUI to resolve once the rubric verdict lands, rather than
        committing the status directly; ``blocked`` commits immediately.

        When no goal is set or ``note`` is empty, nothing is committed
        and the ``ToolMessage`` explains what the model must do instead.
    """
    objective = state.get("_goal_objective")
    if not isinstance(objective, str) or not objective:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content="No active goal is set.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )
    goal_status = coerce_goal_status(state.get("_goal_status")) or "active"
    if goal_status in {"paused", "complete"}:
        if goal_status == "paused":
            message = (
                "The goal is paused. The user must run `/goal resume` before its "
                "status can be updated."
            )
        else:
            message = "The goal is already complete and cannot be updated."
        return Command(
            update={
                "messages": [ToolMessage(content=message, tool_call_id=tool_call_id)]
            }
        )
    clean_note = note.strip()
    if not clean_note:
        # Evidence is required: refuse to commit a status with no justification.
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=(
                            f"Provide a note with evidence before marking the "
                            f"goal {status}."
                        ),
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )
    if status == "complete":
        # Stage completion evidence; the TUI resolves this after the rubric
        # grader's verdict lands on the post-turn checkpoint sync.
        return Command(
            update={
                "_pending_goal_completion_note": clean_note,
                "messages": [
                    ToolMessage(
                        content=(
                            "Goal completion requested. It will be recorded if "
                            "the accepted rubric is satisfied."
                        ),
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )
    # Blocked — commit immediately and clear any pending completion staging.
    update: dict[str, Any] = {
        "_goal_status": status,
        "_goal_status_note": clean_note,
        "_pending_goal_completion_note": None,
    }
    return Command(
        update={
            **update,
            "messages": [
                ToolMessage(
                    content=f"Goal marked {status}. {clean_note}",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


# ---------------------------------------------------------------------------
# Tool definitions (registered by GoalToolsMiddleware.__init__)
# ---------------------------------------------------------------------------


@tool
def get_rubric(
    state: Annotated[dict[str, Any], InjectedState],
) -> RubricSnapshot:
    """Read criteria when the latest state notice says a rubric is active.

    Use this only when the latest goal/rubric state notice reports an active
    rubric. Use ``get_goal`` when a goal is actionable; this tool only reports
    whether criteria are active, the current criteria, and the latest grading
    status.

    Returns:
        Rubric snapshot with ``active``, ``criteria``, and ``grading_status``
        keys.
    """
    return _rubric_snapshot(state)


@tool
def get_goal(
    state: Annotated[dict[str, Any], InjectedState],
) -> GoalSnapshot:
    """Read a goal when the latest state notice says it is actionable.

    Use this only when the latest goal/rubric state notice reports an
    actionable goal. It returns the objective, criteria, lifecycle status,
    and any prior note from authoritative checkpoint state. Paused and
    completed goals report ``active=False`` and must not drive work.

    Returns:
        Goal snapshot with ``active``, ``objective``, ``status``, ``criteria``,
        and ``note`` keys.
    """
    return _goal_snapshot(state)


@tool
def update_goal(
    status: Annotated[
        Literal["complete", "blocked"],
        Field(
            description=(
                "`complete` to attach completion evidence, or `blocked` "
                "when you are stuck and need the user."
            )
        ),
    ],
    note: Annotated[
        str,
        Field(
            description=(
                "Evidence the criteria are satisfied, or the specific "
                "blocker. Required when calling this tool."
            )
        ),
    ],
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict[str, Any], InjectedState],
) -> Command[Any]:
    """Update a goal only when the latest state notice says it is actionable.

    Use ``blocked`` when you cannot proceed without user input. Goals complete
    automatically after a satisfied goal-backed grading turn, so ``complete``
    is optional and only stages its evidence for that result. Do not create,
    pause, resume, clear, or replace goals — those are user-controlled.

    Returns:
        Command that updates goal status and returns a tool message.
    """
    return _update_goal_command(
        status=status,
        note=note,
        tool_call_id=tool_call_id,
        state=state,
    )
