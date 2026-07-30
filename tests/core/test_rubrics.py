from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import SystemMessage, HumanMessage
from dcoder.rubrics.generator import generate_rubric, GOAL_RUBRIC_SYSTEM_PROMPT
from dcoder.rubrics.goal_tools import (
    GoalToolsMiddleware,
    _rubric_snapshot,
    _goal_snapshot,
    _update_goal_command,
)


@patch("dcoder.rubrics.generator.create_model")
def test_generate_rubric(mock_create_model):
    mock_response = MagicMock()
    mock_response.content = "- Must include unit tests\n- Code must pass linter"

    mock_model = MagicMock()
    mock_model.invoke.return_value = mock_response

    mock_create_model.return_value.model = mock_model

    rubric = generate_rubric("Implement OAuth refresh token handling")

    assert "- Must include unit tests" in rubric
    mock_create_model.assert_called_once()

    # Verify model invocation arguments
    call_args = mock_model.invoke.call_args[0][0]
    assert len(call_args) == 2
    assert isinstance(call_args[0], SystemMessage)
    assert GOAL_RUBRIC_SYSTEM_PROMPT in call_args[0].content
    assert isinstance(call_args[1], HumanMessage)
    assert "Implement OAuth refresh token handling" in call_args[1].content


def test_goal_tools_middleware():
    middleware = GoalToolsMiddleware()
    assert len(middleware.tools) == 3
    tool_names = [t.name for t in middleware.tools]
    assert "get_rubric" in tool_names
    assert "get_goal" in tool_names
    assert "update_goal" in tool_names


def test_rubric_snapshot_sources():
    # Goal source
    state_goal = {
        "_goal_objective": "Fix auth bug",
        "_goal_status": "active",
        "_goal_rubric": "unit tests pass",
        "rubric": "unit tests pass",
    }
    snap_goal = _rubric_snapshot(state_goal)
    assert snap_goal["active"] is True
    assert snap_goal["source"] == "goal"
    assert snap_goal["criteria"] == "unit tests pass"

    # Sticky source
    state_sticky = {
        "_sticky_rubric": "no hardcoded secrets",
        "rubric": "no hardcoded secrets",
    }
    snap_sticky = _rubric_snapshot(state_sticky)
    assert snap_sticky["active"] is True
    assert snap_sticky["source"] == "sticky"

    # Invocation source
    state_inv = {
        "rubric": "run pytest -k test_auth",
    }
    snap_inv = _rubric_snapshot(state_inv)
    assert snap_inv["active"] is True
    assert snap_inv["source"] == "invocation"


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
