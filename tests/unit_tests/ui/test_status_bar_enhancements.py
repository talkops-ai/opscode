"""Unit tests for StatusBar enhancements and backend evaluation logic alignment."""

import pytest
from pathlib import Path
from dcoder.ui.app import DCoderApp
from dcoder.ui.status import StatusBar, ModelLabel, BranchLabel
from dcoder.commands.power.goal import GoalState, GoalHandler


@pytest.mark.asyncio
async def test_status_bar_approval_mode_badges():
    app = DCoderApp(defer_server_start=True)
    async with app.run_test() as pilot:
        sb = app.query_one(StatusBar)

        sb.set_approval_mode("manual")
        await pilot.pause()
        indicator = sb.query_one("#auto-approve-indicator")
        assert "manual" in indicator.classes
        assert "manual" in str(indicator.render())

        sb.set_approval_mode("auto")
        await pilot.pause()
        assert "auto" in indicator.classes
        assert "auto" in str(indicator.render())

        sb.set_approval_mode("yolo")
        await pilot.pause()
        assert "yolo" in indicator.classes
        assert "YOLO" in str(indicator.render())


@pytest.mark.asyncio
async def test_status_bar_tokens_and_cost():
    app = DCoderApp(defer_server_start=True)
    async with app.run_test() as pilot:
        sb = app.query_one(StatusBar)

        sb.set_tokens(29800)
        sb.set_cost(0.38)
        await pilot.pause()

        tokens_widget = sb.query_one("#tokens-display")
        assert tokens_widget.display is True
        content = str(tokens_widget.render())
        assert "29.8K tokens" in content
        assert "$0.38" in content


@pytest.mark.asyncio
async def test_status_bar_model_label_and_effort():
    app = DCoderApp(defer_server_start=True)
    async with app.run_test() as pilot:
        sb = app.query_one(StatusBar)

        sb.set_model(provider="google_genai", model="gemini-3.6-flash", effort="medium")
        await pilot.pause()

        label = sb.query_one("#model-display", ModelLabel)
        assert label.provider == "google_genai"
        assert label.model == "gemini-3.6-flash"
        assert label.effort == "medium"


@pytest.mark.asyncio
async def test_status_bar_rubric_label_sync():
    app = DCoderApp(defer_server_start=True)
    async with app.run_test() as pilot:
        sb = app.query_one(StatusBar)
        state = GoalState()

        state.rubric = "Check production grade standards"
        GoalHandler._sync_status_rubric(app, state)
        await pilot.pause()

        rubric_widget = sb.query_one("#rubric-display")
        assert rubric_widget.display is True
        assert "✓ Rubric set" in str(rubric_widget.render())

        state.objective = "Check s3 module"
        state.status = "complete"
        GoalHandler._sync_status_rubric(app, state)
        await pilot.pause()
        assert "✓ Goal complete" in str(rubric_widget.render())

        state.status = "paused"
        GoalHandler._sync_status_rubric(app, state)
        await pilot.pause()
        assert "⏸ Goal paused" in str(rubric_widget.render())


@pytest.mark.asyncio
async def test_status_bar_cwd_and_branch():
    home = Path.home()
    test_path = home / "Documents" / "work" / "talkops" / "terraform-example-modules"
    app = DCoderApp(defer_server_start=True)

    async with app.run_test() as pilot:
        sb = app.query_one(StatusBar)
        formatted_cwd = sb._format_cwd(str(test_path))
        assert formatted_cwd == "~/Documents/work/talkops/terraform-example-modules"

        sb.branch = "develop"
        await pilot.pause()

        branch_label = sb.query_one("#branch-display", BranchLabel)
        assert branch_label.branch == "develop"


@pytest.mark.asyncio
async def test_reset_thread_usage():
    app = DCoderApp(defer_server_start=True)
    async with app.run_test() as pilot:
        sb = app.query_one(StatusBar)
        sb.set_tokens(19000)
        sb.set_cost(0.12)
        await pilot.pause()

        tokens_widget = sb.query_one("#tokens-display")
        assert "19.0K tokens" in str(tokens_widget.render())

        app._reset_thread_usage(0.0, 0)
        await pilot.pause()

        assert app._context_tokens == 0
        assert app._session_cost_usd == 0.0
        assert tokens_widget.display is False


def test_default_effort_for_reasoning_models():
    from dcoder.model.reasoning import default_effort_for_model

    assert default_effort_for_model("google_genai:gemini-3.6-flash") == "medium"
    assert default_effort_for_model("openai:gpt-4o") is None

