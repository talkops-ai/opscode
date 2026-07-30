"""Goal management tools exposed to the agent."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypedDict, TypeVar, Callable, Awaitable
from typing_extensions import override

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

logger = logging.getLogger(__name__)

GoalStatus = Literal["active", "complete", "blocked"]

GOAL_TOOLS_SYSTEM_PROMPT = """## Goal and Rubric Tools

Use `get_rubric` to inspect active acceptance criteria before deciding whether work is complete.
When a goal is active, use `get_goal` to inspect the objective and current status.
Use `update_goal` only when you have evidence that the goal is complete or blocked."""

class RubricSnapshot(TypedDict):
    active: bool
    criteria: str | None
    source: Literal["goal", "sticky", "invocation"] | None
    grading_status: str | None

class GoalSnapshot(TypedDict):
    active: bool
    objective: str | None
    status: GoalStatus | None
    criteria: str | None
    note: str | None

def _rubric_snapshot(state: dict[str, Any]) -> RubricSnapshot:
    criteria = state.get("rubric") or state.get("_goal_rubric") or state.get("_sticky_rubric")
    source: Literal["goal", "sticky", "invocation"] | None = None
    if criteria:
        if state.get("_goal_rubric") == criteria:
            source = "goal"
        elif state.get("_sticky_rubric") == criteria:
            source = "sticky"
        else:
            source = "invocation"
            
    return {
        "active": criteria is not None,
        "criteria": criteria,
        "source": source,
        "grading_status": state.get("_rubric_status"),
    }

def _goal_snapshot(state: dict[str, Any]) -> GoalSnapshot:
    objective = state.get("_goal_objective")
    rubric = _rubric_snapshot(state)
    if objective is None:
        return {
            "active": False,
            "objective": None,
            "status": None,
            "criteria": rubric["criteria"],
            "note": None,
        }
    status = state.get("_goal_status") or "active"
    note = state.get("_goal_status_note")
    return {
        "active": status != "complete",
        "objective": objective,
        "status": status,
        "criteria": rubric["criteria"],
        "note": note,
    }

def _update_goal_command(
    *,
    status: Literal["complete", "blocked"],
    note: str,
    tool_call_id: str,
    state: dict[str, Any],
) -> Command[Any]:
    objective = state.get("_goal_objective")
    if not objective:
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
    clean_note = note.strip()
    if not clean_note:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Provide a note with evidence before marking the goal {status}.",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )
    if status == "complete":
        return Command(
            update={
                "_goal_status": "complete",
                "_goal_status_note": clean_note,
                "messages": [
                    ToolMessage(
                        content="Goal completion requested. It will be recorded if the accepted rubric is satisfied.",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )
    return Command(
        update={
            "_goal_status": status,
            "_goal_status_note": clean_note,
            "messages": [
                ToolMessage(
                    content=f"Goal marked {status}. {clean_note}",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )

class GoalToolsMiddleware(AgentMiddleware[Any, Any]):
    """Expose goal tools to the agent."""

    def __init__(self) -> None:
        super().__init__()

        @tool
        def get_rubric(
            state: Annotated[dict[str, Any], InjectedState],
        ) -> RubricSnapshot:
            """Read the current acceptance criteria used to evaluate completion."""
            return _rubric_snapshot(state)

        @tool
        def get_goal(
            state: Annotated[dict[str, Any], InjectedState],
        ) -> GoalSnapshot:
            """Read the current persistent goal and acceptance criteria."""
            return _goal_snapshot(state)

        @tool
        def update_goal(
            status: Literal["complete", "blocked"],
            note: str,
            tool_call_id: Annotated[str, InjectedToolCallId],
            state: Annotated[dict[str, Any], InjectedState],
        ) -> Command[Any]:
            """Mark the current goal complete or blocked with evidence."""
            return _update_goal_command(
                status=status,
                note=note,
                tool_call_id=tool_call_id,
                state=state,
            )

        self.tools = [get_rubric, get_goal, update_goal]

    def _request_with_goal_system_context(
        self,
        request: ModelRequest[Any],
    ) -> ModelRequest[Any]:
        prompt = GOAL_TOOLS_SYSTEM_PROMPT
        content: list[Any]
        if request.system_message is not None:
            content = [
                *request.system_message.content_blocks,
                {"type": "text", "text": f"\n\n{prompt}"},
            ]
        else:
            content = [{"type": "text", "text": prompt}]
        return request.override(
            system_message=SystemMessage(content=content)
        )

    @override
    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        return handler(self._request_with_goal_system_context(request))

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        return await handler(self._request_with_goal_system_context(request))
