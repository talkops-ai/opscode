from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import SystemMessage, HumanMessage
from dcoder.rubrics.generator import generate_rubric
from dcoder.rubrics.goal_tools import (
    GoalToolsMiddleware,
    _rubric_snapshot,
    _goal_snapshot,
    _update_goal_command,
)





def test_goal_tools_middleware():
    middleware = GoalToolsMiddleware()
    assert len(middleware.tools) == 3
    tool_names = [t.name for t in middleware.tools]
    assert "get_rubric" in tool_names
    assert "get_goal" in tool_names
    assert "update_goal" in tool_names





def test_goal_snapshot_active_status():
    state_active = {
        "_goal_objective": "Migrate DB",
        "_goal_status": "active",
        "_goal_rubric": "zero downtime",
    }
    snap_active = _goal_snapshot(state_active)
    assert snap_active["active"] is True
    assert snap_active["objective"] == "Migrate DB"

    state_blocked = {
        "_goal_objective": "Migrate DB",
        "_goal_status": "blocked",
        "_goal_status_note": "Waiting for DB credentials",
    }
    snap_blocked = _goal_snapshot(state_blocked)
    assert snap_blocked["active"] is True
    assert snap_blocked["note"] == "Waiting for DB credentials"

    state_complete = {
        "_goal_objective": "Migrate DB",
        "_goal_status": "complete",
    }
    snap_complete = _goal_snapshot(state_complete)
    assert snap_complete["active"] is False


def test_update_goal_command():
    state_no_goal = {}
    cmd = _update_goal_command(
        status="complete",
        note="Done",
        tool_call_id="tc_1",
        state=state_no_goal,
    )
    assert cmd.update is not None
    assert "No active goal is set" in cmd.update["messages"][0].content

    state_valid = {"_goal_objective": "Add tests"}
    cmd_blocked = _update_goal_command(
        status="blocked",
        note="Need API key",
        tool_call_id="tc_2",
        state=state_valid,
    )
    assert cmd_blocked.update is not None
    assert cmd_blocked.update["_goal_status"] == "blocked"
    assert cmd_blocked.update["_goal_status_note"] == "Need API key"
