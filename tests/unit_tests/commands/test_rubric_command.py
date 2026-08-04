"""Tests for the /rubric command: set, show, clear, and file."""

from __future__ import annotations

import pytest

from dcoder.commands.power.goal import get_goal_state
from dcoder.commands.power.rubric import RubricHandler


class TestRubricCommand:
    @pytest.mark.asyncio
    async def test_rubric_set_stores_criteria(self, mock_app, make_ctx):
        """/rubric set <criteria> should store directly in the goal state."""
        state = get_goal_state(mock_app)
        
        ctx = make_ctx(
            args="set - All tests pass\n- No regressions",
            raw="/rubric set - All tests pass\n- No regressions",
            app=mock_app,
        )
        res = await RubricHandler().execute(ctx)
        
        assert res.success
        assert state.rubric == "- All tests pass\n- No regressions"
        mock_app._persist_goal_rubric_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_rubric_clear(self, mock_app, make_ctx):
        """/rubric clear should remove the rubric but keep the objective."""
        state = get_goal_state(mock_app)
        state.objective = "Test objective"
        state.rubric = "- Some criteria"

        ctx = make_ctx(args="clear", raw="/rubric clear", app=mock_app)
        res = await RubricHandler().execute(ctx)
        
        assert res.success
        assert state.rubric is None
        assert state.objective == "Test objective"  # Preserved
        mock_app._persist_goal_rubric_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_rubric_show_empty(self, mock_app, make_ctx):
        """/rubric show with no rubric should indicate none set."""
        ctx = make_ctx(args="show", raw="/rubric show", app=mock_app)
        res = await RubricHandler().execute(ctx)
        
        assert res.success
        assert res.message is not None and "No rubric set." in res.message

    @pytest.mark.asyncio
    async def test_rubric_show_with_criteria(self, mock_app, make_ctx):
        """/rubric show should render the current rubric."""
        state = get_goal_state(mock_app)
        state.rubric = "- Valid criteria"
        
        ctx = make_ctx(args="show", raw="/rubric show", app=mock_app)
        res = await RubricHandler().execute(ctx)
        
        assert res.success
        assert res.message is not None and "- Valid criteria" in res.message

    @pytest.mark.asyncio
    async def test_rubric_file_reads_path(self, mock_app, make_ctx, tmp_path):
        """/rubric file <path> should read criteria from the file."""
        state = get_goal_state(mock_app)
        
        criteria_file = tmp_path / "criteria.md"
        criteria_file.write_text("- Test passes\n- Lints clean")

        ctx = make_ctx(
            args=f"file {criteria_file}",
            raw=f"/rubric file {criteria_file}",
            app=mock_app,
        )
        res = await RubricHandler().execute(ctx)
        
        assert res.success
        assert state.rubric == "- Test passes\n- Lints clean"
        mock_app._persist_goal_rubric_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_rubric_file_not_found(self, mock_app, make_ctx):
        """/rubric file <path> should fail gracefully if file doesn't exist."""
        ctx = make_ctx(
            args="file /does/not/exist.md",
            raw="/rubric file /does/not/exist.md",
            app=mock_app,
        )
        res = await RubricHandler().execute(ctx)
        
        assert not res.success
        assert res.message is not None and "File not found" in res.message
