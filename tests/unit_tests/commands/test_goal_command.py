"""Tests for the /goal command: set, show, clear, pause, resume, and amend."""

from __future__ import annotations

import pytest

from dcoder.commands.power.goal import GoalHandler, get_goal_state


class TestGoalCommand:
    @pytest.mark.asyncio
    async def test_goal_show_no_goal_set(self, mock_app, make_ctx):
        """/goal show with no goal set."""
        ctx = make_ctx(args="show", raw="/goal show", app=mock_app)
        res = await GoalHandler().execute(ctx)
        
        assert res.success
        assert res.message is not None and "No goal set" in res.message
        assert res.message is not None and "/goal <objective>" in res.message

    @pytest.mark.asyncio
    async def test_goal_set_triggers_criteria_request(self, mock_app, make_ctx):
        """/goal <objective> should trigger a criteria generation request."""
        ctx = make_ctx(args="Deploy VPC", raw="/goal Deploy VPC", app=mock_app)
        res = await GoalHandler().execute(ctx)
        
        assert res.success
        assert res.message is None
        
        # Verify the app method was called with the right objective
        mock_app._run_goal_criteria_request.assert_called_once()
        req = mock_app._run_goal_criteria_request.call_args[0][0]
        assert req["objective"] == "Deploy VPC"
        assert req["kind"] == "create"

    @pytest.mark.asyncio
    async def test_goal_clear_resets_state(self, mock_app, make_ctx):
        """/goal clear should reset objective and status but keep grader settings."""
        state = get_goal_state(mock_app)
        state.objective = "Test objective"
        state.status = "active"
        state.rubric_model = "gpt-4"

        ctx = make_ctx(args="clear", raw="/goal clear", app=mock_app)
        res = await GoalHandler().execute(ctx)
        
        assert res.success
        assert state.objective is None
        assert state.status is None
        assert state.rubric_model == "gpt-4"  # Preserved
        
        # Verify it persisted the state change
        mock_app._persist_goal_rubric_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_goal_pause_active(self, mock_app, make_ctx):
        """/goal pause on an active goal should set status to paused."""
        state = get_goal_state(mock_app)
        state.objective = "Test objective"
        state.status = "active"

        ctx = make_ctx(args="pause", raw="/goal pause", app=mock_app)
        res = await GoalHandler().execute(ctx)
        
        assert res.success
        assert state.status == "paused"
        mock_app._persist_goal_rubric_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_goal_resume_paused(self, mock_app, make_ctx):
        """/goal resume on a paused goal should set status to active."""
        state = get_goal_state(mock_app)
        state.objective = "Test objective"
        state.status = "paused"

        ctx = make_ctx(args="resume", raw="/goal resume", app=mock_app)
        res = await GoalHandler().execute(ctx)
        
        assert res.success
        assert state.status == "active"
        mock_app._persist_goal_rubric_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_goal_max_iterations(self, mock_app, make_ctx):
        """/goal max-iterations <n> should update the grader setting."""
        state = get_goal_state(mock_app)
        
        ctx = make_ctx(args="max-iterations 5", raw="/goal max-iterations 5", app=mock_app)
        res = await GoalHandler().execute(ctx)
        
        assert res.success
        assert state.rubric_max_iterations == 5
        # Note: /goal max-iterations does not trigger _persist_goal_rubric_state
        assert mock_app._persist_goal_rubric_state.call_count == 0

    @pytest.mark.asyncio
    async def test_goal_amend_sends_feedback(self, mock_app, make_ctx):
        """/goal amend <feedback> should trigger an amend criteria request."""
        state = get_goal_state(mock_app)
        state.objective = "Original objective"
        state.rubric = "- Original criteria"
        
        ctx = make_ctx(args="amend add tests", raw="/goal amend add tests", app=mock_app)
        res = await GoalHandler().execute(ctx)
        
        assert res.success
        
        mock_app._run_goal_criteria_request.assert_called_once()
        req = mock_app._run_goal_criteria_request.call_args[0][0]
        assert req["objective"] == "Original objective"
        assert req["criteria"] == "- Original criteria"
        assert req["feedback"] == "add tests"
        assert req["kind"] == "amend"
