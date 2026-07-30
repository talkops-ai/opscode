"""Tests for Phase 4 — Power User Commands.

Covers: /goal, /rubric, /review, /memory, /btw, /loop, /tasks,
        /agents, /skill-creator, /skill:<name>, /reload, /restart, /update
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dcoder.commands._base import CommandContext, CommandResult


def _make_ctx(
    *,
    args: str = "",
    raw: str = "",
    app: object | None = None,
    model_spec: str | None = None,
) -> CommandContext:
    """Create a minimal CommandContext for testing."""
    return CommandContext(
        app=app or MagicMock(spec=[]),
        raw_command=raw or f"/test {args}".strip(),
        args=args,
        model_spec=model_spec,
    )


# ── /agents ─────────────────────────────────────────────


class TestAgentsHandler:
    @pytest.mark.asyncio
    async def test_agents_text_fallback(self):
        from dcoder.commands.power.agents import AgentsHandler

        ctx = _make_ctx(raw="/agents")
        res = await AgentsHandler().execute(ctx)
        assert res.success
        # No agent dirs exist, should show "no configurations" message
        assert "No agent configurations" in (res.message or "")

    @pytest.mark.asyncio
    async def test_agents_opens_selector(self):
        from dcoder.commands.power.agents import AgentsHandler

        mock_app = MagicMock()
        mock_app._show_agent_selector = MagicMock()
        ctx = _make_ctx(raw="/agents", app=mock_app)
        res = await AgentsHandler().execute(ctx)
        assert res.success
        mock_app._show_agent_selector.assert_called_once()


# ── /btw ────────────────────────────────────────────────


class TestBtwHandler:
    @pytest.mark.asyncio
    async def test_btw_no_args_error(self):
        from dcoder.commands.power.btw import BtwHandler

        handler = BtwHandler()
        ctx = _make_ctx(args="", raw="/btw")
        error = handler.validate(ctx)
        assert error is not None
        assert "Usage" in error

    @pytest.mark.asyncio
    async def test_btw_sends_ephemeral(self):
        from dcoder.commands.power.btw import BtwHandler

        mock_app = MagicMock()
        mock_app._send_ephemeral_message = AsyncMock()
        ctx = _make_ctx(args="what is terraform?", raw="/btw what is terraform?", app=mock_app)
        res = await BtwHandler().execute(ctx)
        assert res.success
        mock_app._send_ephemeral_message.assert_called_once()
        call_arg = mock_app._send_ephemeral_message.call_args[0][0]
        assert "ASIDE" in call_arg
        assert "what is terraform?" in call_arg


# ── /tasks ──────────────────────────────────────────────


class TestTasksHandler:
    @pytest.mark.asyncio
    async def test_tasks_add(self):
        from dcoder.commands.power.tasks import TasksHandler, get_task_store

        store = get_task_store()
        store._tasks.clear()
        store._next_id = 1

        ctx = _make_ctx(args="add Fix the CI pipeline", raw="/tasks add Fix the CI pipeline")
        res = await TasksHandler().execute(ctx)
        assert res.success
        assert "#1" in (res.message or "")
        assert "Fix the CI pipeline" in (res.message or "")

    @pytest.mark.asyncio
    async def test_tasks_done(self):
        from dcoder.commands.power.tasks import TasksHandler, get_task_store

        store = get_task_store()
        store._tasks.clear()
        store._next_id = 1
        store.add("Test task")

        ctx = _make_ctx(args="done 1", raw="/tasks done 1")
        res = await TasksHandler().execute(ctx)
        assert res.success
        assert "Completed" in (res.message or "")

    @pytest.mark.asyncio
    async def test_tasks_list_empty(self):
        from dcoder.commands.power.tasks import TasksHandler, get_task_store

        store = get_task_store()
        store._tasks.clear()

        ctx = _make_ctx(args="", raw="/tasks")
        res = await TasksHandler().execute(ctx)
        assert res.success
        assert "No tasks" in (res.message or "")

    @pytest.mark.asyncio
    async def test_tasks_clear(self):
        from dcoder.commands.power.tasks import TasksHandler, get_task_store

        store = get_task_store()
        store._tasks.clear()
        store._next_id = 1
        task = store.add("Done task")
        store.done(task.id)

        ctx = _make_ctx(args="clear", raw="/tasks clear")
        res = await TasksHandler().execute(ctx)
        assert res.success
        assert "1" in (res.message or "")


# ── /review ─────────────────────────────────────────────


class TestReviewHandler:
    @pytest.mark.asyncio
    async def test_review_no_git(self):
        from dcoder.commands.power.review import ReviewHandler

        with patch("dcoder.commands.power.review._get_diff", return_value=None):
            ctx = _make_ctx(raw="/review")
            res = await ReviewHandler().execute(ctx)
            assert not res.success
            assert "Git" in (res.message or "")

    @pytest.mark.asyncio
    async def test_review_clean_tree(self):
        from dcoder.commands.power.review import ReviewHandler

        with patch("dcoder.commands.power.review._get_diff", return_value=""):
            ctx = _make_ctx(raw="/review")
            res = await ReviewHandler().execute(ctx)
            assert res.success
            assert "clean" in (res.message or "").lower()


# ── /memory ─────────────────────────────────────────────


class TestMemoryHandler:
    @pytest.mark.asyncio
    async def test_memory_show_empty(self):
        from dcoder.commands.power.memory import MemoryHandler

        with patch("dcoder.commands.power.memory._detect_project_root", return_value=None):
            ctx = _make_ctx(args="show", raw="/memory show")
            res = await MemoryHandler().execute(ctx)
            assert res.success
            assert "No memories" in (res.message or "")

    @pytest.mark.asyncio
    async def test_memory_save_and_get(self, tmp_path):
        from dcoder.commands.power.memory import MemoryHandler

        with patch(
            "dcoder.commands.power.memory._detect_project_root",
            return_value=tmp_path,
        ):
            ctx = _make_ctx(
                args="save test-key Always use terraform fmt",
                raw="/memory save test-key Always use terraform fmt",
            )
            res = await MemoryHandler().execute(ctx)
            assert res.success
            assert "saved" in (res.message or "").lower()

            # Verify file exists
            assert (tmp_path / ".dcoder" / "memory" / "test-key.md").exists()

    @pytest.mark.asyncio
    async def test_remember_with_text(self, tmp_path):
        from dcoder.commands.power.memory import MemoryHandler

        with patch(
            "dcoder.commands.power.memory._detect_project_root",
            return_value=tmp_path,
        ):
            ctx = _make_ctx(
                args="prefer terraform fmt over tofu",
                raw="/remember prefer terraform fmt over tofu",
            )
            # Override cmd_name detection
            ctx_dict = ctx.__dict__.copy()
            ctx_new = CommandContext(
                app=ctx.app,
                raw_command="/remember prefer terraform fmt over tofu",
                args="prefer terraform fmt over tofu",
            )
            res = await MemoryHandler().execute(ctx_new)
            assert res.success
            assert "saved" in (res.message or "").lower()


# ── /goal ───────────────────────────────────────────────


class TestGoalHandler:
    @pytest.mark.asyncio
    async def test_goal_show_empty(self):
        from dcoder.commands.power.goal import GoalHandler

        mock_app = MagicMock(spec=[])
        ctx = _make_ctx(args="show", raw="/goal show", app=mock_app)
        res = await GoalHandler().execute(ctx)
        assert res.success
        # Should show full usage text when no goal is set
        msg = res.message or ""
        assert "No goal set" in msg
        assert "/goal <objective>" in msg
        assert "/goal amend <feedback>" in msg
        assert "/goal model" in msg
        assert "/goal max-iterations" in msg

    @pytest.mark.asyncio
    async def test_goal_no_args_shows_usage(self):
        from dcoder.commands.power.goal import GoalHandler

        mock_app = MagicMock(spec=[])
        ctx = _make_ctx(args="", raw="/goal", app=mock_app)
        res = await GoalHandler().execute(ctx)
        assert res.success
        msg = res.message or ""
        assert "No goal set" in msg
        assert "draft a checklist" in msg

    @pytest.mark.asyncio
    async def test_goal_set_objective(self):
        from dcoder.commands.power.goal import GoalHandler

        mock_rubric = "- Criterion 1\n- Criterion 2"
        mock_app = MagicMock(spec=[])

        with patch(
            "dcoder.commands.power.goal._generate_rubric",
            return_value=mock_rubric,
        ):
            ctx = _make_ctx(
                args="Deploy a VPC with 3 subnets",
                raw="/goal Deploy a VPC with 3 subnets",
                app=mock_app,
            )
            res = await GoalHandler().execute(ctx)
            assert res.success
            assert "Goal set" in (res.message or "")

    @pytest.mark.asyncio
    async def test_goal_clear(self):
        from dcoder.commands.power.goal import GoalHandler, get_goal_state

        mock_app = MagicMock(spec=[])
        state = get_goal_state(mock_app)
        state.objective = "Test objective"
        state.status = "active"

        ctx = _make_ctx(args="clear", raw="/goal clear", app=mock_app)
        res = await GoalHandler().execute(ctx)
        assert res.success
        assert state.objective is None

    @pytest.mark.asyncio
    async def test_goal_pause_resume(self):
        from dcoder.commands.power.goal import GoalHandler, get_goal_state

        mock_app = MagicMock(spec=[])
        state = get_goal_state(mock_app)
        state.objective = "Test objective"
        state.status = "active"

        # Pause
        ctx = _make_ctx(args="pause", raw="/goal pause", app=mock_app)
        res = await GoalHandler().execute(ctx)
        assert res.success
        assert state.status == "paused"

        # Resume
        ctx = _make_ctx(args="resume", raw="/goal resume", app=mock_app)
        res = await GoalHandler().execute(ctx)
        assert res.success
        assert state.status == "active"

    @pytest.mark.asyncio
    async def test_goal_pause_blocked_shows_message(self):
        from dcoder.commands.power.goal import GoalHandler, get_goal_state

        mock_app = MagicMock(spec=[])
        state = get_goal_state(mock_app)
        state.objective = "Deploy VPC"
        state.status = "blocked"

        ctx = _make_ctx(args="pause", raw="/goal pause", app=mock_app)
        res = await GoalHandler().execute(ctx)
        assert res.success
        assert "blocked" in (res.message or "").lower()

    @pytest.mark.asyncio
    async def test_goal_resume_not_paused(self):
        from dcoder.commands.power.goal import GoalHandler, get_goal_state

        mock_app = MagicMock(spec=[])
        state = get_goal_state(mock_app)
        state.objective = "Deploy VPC"
        state.status = "active"

        ctx = _make_ctx(args="resume", raw="/goal resume", app=mock_app)
        res = await GoalHandler().execute(ctx)
        assert not res.success
        assert "not paused" in (res.message or "").lower()

    @pytest.mark.asyncio
    async def test_goal_model_set_and_clear(self):
        from dcoder.commands.power.goal import GoalHandler, get_goal_state

        mock_app = MagicMock(spec=[])
        state = get_goal_state(mock_app)

        # Set grader model
        ctx = _make_ctx(args="model openai:gpt-5.1", raw="/goal model openai:gpt-5.1", app=mock_app)
        res = await GoalHandler().execute(ctx)
        assert res.success
        assert state.rubric_model == "openai:gpt-5.1"

        # Clear
        ctx = _make_ctx(args="model clear", raw="/goal model clear", app=mock_app)
        res = await GoalHandler().execute(ctx)
        assert res.success
        assert state.rubric_model is None

    @pytest.mark.asyncio
    async def test_goal_model_multiword_is_objective(self):
        """Multi-word 'model my infrastructure' should be a new objective, not grader."""
        from dcoder.commands.power.goal import GoalHandler

        mock_rubric = "- Criterion"
        mock_app = MagicMock(spec=[])

        with patch(
            "dcoder.commands.power.goal._generate_rubric",
            return_value=mock_rubric,
        ):
            ctx = _make_ctx(
                args="model my infrastructure with terraform",
                raw="/goal model my infrastructure with terraform",
                app=mock_app,
            )
            res = await GoalHandler().execute(ctx)
            assert res.success
            assert "Goal set" in (res.message or "")

    @pytest.mark.asyncio
    async def test_goal_max_iterations_set(self):
        from dcoder.commands.power.goal import GoalHandler, get_goal_state

        mock_app = MagicMock(spec=[])
        state = get_goal_state(mock_app)

        ctx = _make_ctx(args="max-iterations 5", raw="/goal max-iterations 5", app=mock_app)
        res = await GoalHandler().execute(ctx)
        assert res.success
        assert state.rubric_max_iterations == 5

    @pytest.mark.asyncio
    async def test_goal_show_with_active_goal(self):
        from dcoder.commands.power.goal import GoalHandler, get_goal_state

        mock_app = MagicMock(spec=[])
        state = get_goal_state(mock_app)
        state.objective = "Deploy a VPC"
        state.status = "active"
        state.rubric = "- All subnets created"
        state.rubric_model = "openai:gpt-5.1"
        state.rubric_max_iterations = 3

        ctx = _make_ctx(args="show", raw="/goal show", app=mock_app)
        res = await GoalHandler().execute(ctx)
        assert res.success
        msg = res.message or ""
        assert "Deploy a VPC" in msg
        assert "All subnets created" in msg
        assert "openai:gpt-5.1" in msg
        assert "3" in msg
        assert "active for this thread" in msg

    @pytest.mark.asyncio
    async def test_is_grader_alias_arg(self):
        from dcoder.commands.power.goal import _is_grader_alias_arg

        assert _is_grader_alias_arg("") is True
        assert _is_grader_alias_arg("clear") is True
        assert _is_grader_alias_arg("openai:gpt-5.1") is True
        assert _is_grader_alias_arg("5") is True
        assert _is_grader_alias_arg("my infrastructure") is False
        assert _is_grader_alias_arg("deploy a VPC with subnets") is False


# ── /rubric ─────────────────────────────────────────────


class TestRubricHandler:
    @pytest.mark.asyncio
    async def test_rubric_set(self):
        from dcoder.commands.power.goal import get_goal_state
        from dcoder.commands.power.rubric import RubricHandler

        mock_app = MagicMock(spec=[])
        ctx = _make_ctx(
            args="set - All tests pass\n- No regressions",
            raw="/rubric set - All tests pass\n- No regressions",
            app=mock_app,
        )
        res = await RubricHandler().execute(ctx)
        assert res.success
        state = get_goal_state(mock_app)
        assert state.rubric is not None

    @pytest.mark.asyncio
    async def test_rubric_clear(self):
        from dcoder.commands.power.goal import get_goal_state
        from dcoder.commands.power.rubric import RubricHandler

        mock_app = MagicMock(spec=[])
        state = get_goal_state(mock_app)
        state.rubric = "- Some criteria"

        ctx = _make_ctx(args="clear", raw="/rubric clear", app=mock_app)
        res = await RubricHandler().execute(ctx)
        assert res.success
        assert state.rubric is None

    @pytest.mark.asyncio
    async def test_rubric_show(self):
        from dcoder.commands.power.rubric import RubricHandler

        mock_app = MagicMock(spec=[])
        ctx = _make_ctx(args="show", raw="/rubric show", app=mock_app)
        res = await RubricHandler().execute(ctx)
        assert res.success

    @pytest.mark.asyncio
    async def test_rubric_file(self, tmp_path):
        from dcoder.commands.power.goal import get_goal_state
        from dcoder.commands.power.rubric import RubricHandler

        criteria_file = tmp_path / "criteria.md"
        criteria_file.write_text("- Test passes\n- Lints clean")

        mock_app = MagicMock(spec=[])
        ctx = _make_ctx(
            args=f"file {criteria_file}",
            raw=f"/rubric file {criteria_file}",
            app=mock_app,
        )
        res = await RubricHandler().execute(ctx)
        assert res.success
        state = get_goal_state(mock_app)
        assert "Test passes" in (state.rubric or "")


# ── /loop ───────────────────────────────────────────────


class TestLoopHandler:
    @pytest.mark.asyncio
    async def test_loop_interval_parse(self):
        from dcoder.commands.power.loop import _parse_interval

        assert _parse_interval("30s") == 30
        assert _parse_interval("5m") == 300
        assert _parse_interval("1h") == 3600
        assert _parse_interval("2d") == 172800

    @pytest.mark.asyncio
    async def test_loop_show_empty(self):
        from dcoder.commands.power.loop import LoopHandler

        mock_app = MagicMock(spec=[])
        ctx = _make_ctx(args="show", raw="/loop show", app=mock_app)
        res = await LoopHandler().execute(ctx)
        assert res.success
        assert "No active loops" in (res.message or "")

    @pytest.mark.asyncio
    async def test_loop_start(self):
        from dcoder.commands.power.loop import LoopHandler, get_loop_manager

        mock_app = MagicMock(spec=[])
        manager = get_loop_manager(mock_app)

        ctx = _make_ctx(
            args="10s check status",
            raw="/loop 10s check status",
            app=mock_app,
        )
        res = await LoopHandler().execute(ctx)
        assert res.success
        assert "Loop started" in (res.message or "")

        # Clean up
        await manager.stop()

    @pytest.mark.asyncio
    async def test_loop_stop(self):
        from dcoder.commands.power.loop import LoopHandler, get_loop_manager

        mock_app = MagicMock(spec=[])
        manager = get_loop_manager(mock_app)
        instance = await manager.start("10s", "test", app=mock_app)

        ctx = _make_ctx(
            args=f"stop {instance.id}",
            raw=f"/loop stop {instance.id}",
            app=mock_app,
        )
        res = await LoopHandler().execute(ctx)
        assert res.success
        assert "Stopped" in (res.message or "")


# ── /skill:<name> ───────────────────────────────────────


class TestSkillInvokeHandler:
    @pytest.mark.asyncio
    async def test_skill_invoke_parse(self):
        from dcoder.skills.invocation import parse_skill_command

        name, args = parse_skill_command("/skill:web-research find CVEs")
        assert name == "web-research"
        assert args == "find CVEs"

    @pytest.mark.asyncio
    async def test_skill_invoke_empty(self):
        from dcoder.skills.invocation import parse_skill_command

        name, args = parse_skill_command("/skill:")
        assert name == ""
        assert args == ""

    @pytest.mark.asyncio
    async def test_skill_invoke_missing(self):
        from dcoder.commands.power.skill_invoke import SkillInvokeHandler

        mock_app = MagicMock()
        mock_app.get_discovered_skills = MagicMock(return_value=[])
        ctx = _make_ctx(
            args="",
            raw="/skill:nonexistent do stuff",
            app=mock_app,
        )
        res = await SkillInvokeHandler().execute(ctx)
        assert not res.success
        assert "not found" in (res.message or "").lower()


# ── /skill-creator ──────────────────────────────────────


class TestSkillCreatorHandler:
    @pytest.mark.asyncio
    async def test_skill_creator_rewrites(self):
        from dcoder.commands.power.skill_creator import SkillCreatorHandler

        mock_app = MagicMock()
        mock_app._handle_skill_command = AsyncMock()
        ctx = _make_ctx(args="", raw="/skill-creator", app=mock_app)
        res = await SkillCreatorHandler().execute(ctx)
        assert res.success
        mock_app._handle_skill_command.assert_called_once_with("/skill:skill-creator")

    @pytest.mark.asyncio
    async def test_skill_creator_with_args(self):
        from dcoder.commands.power.skill_creator import SkillCreatorHandler

        mock_app = MagicMock()
        mock_app._handle_skill_command = AsyncMock()
        ctx = _make_ctx(args="my-new-skill", raw="/skill-creator my-new-skill", app=mock_app)
        res = await SkillCreatorHandler().execute(ctx)
        assert res.success
        mock_app._handle_skill_command.assert_called_once_with("/skill:skill-creator my-new-skill")


# ── /reload ─────────────────────────────────────────────


class TestReloadHandler:
    @pytest.mark.asyncio
    async def test_reload_clears_cache(self):
        from dcoder.commands.power.runtime import ReloadHandler

        mock_app = MagicMock()
        mock_app._discover_skills = MagicMock()
        mock_app._discover_plugins = MagicMock()
        mock_app.reload_css = MagicMock()

        ctx = _make_ctx(raw="/reload", app=mock_app)
        res = await ReloadHandler().execute(ctx)
        assert res.success
        assert "Reloaded" in (res.message or "")


# ── /restart ────────────────────────────────────────────


class TestRestartHandler:
    @pytest.mark.asyncio
    async def test_restart_no_server(self):
        from dcoder.commands.power.runtime import RestartHandler

        mock_app = MagicMock(spec=[])
        ctx = _make_ctx(raw="/restart", app=mock_app)
        res = await RestartHandler().execute(ctx)
        assert res.success
        assert "reloaded" in (res.message or "").lower()


# ── /update ─────────────────────────────────────────────


class TestUpdateHandler:
    @pytest.mark.asyncio
    async def test_update_unknown_option(self):
        from dcoder.commands.power.runtime import UpdateHandler

        ctx = _make_ctx(args="--invalid", raw="/update --invalid")
        res = await UpdateHandler().execute(ctx)
        assert not res.success
        assert "Unknown" in (res.message or "")

    @pytest.mark.asyncio
    async def test_update_checks_version(self):
        from dcoder.commands.power.runtime import UpdateHandler

        with patch(
            "dcoder.commands.power.runtime._check_pypi_version",
            return_value=None,
        ):
            ctx = _make_ctx(raw="/update")
            res = await UpdateHandler().execute(ctx)
            assert res.success
            assert "Could not determine" in (res.message or "")


# ── Memory Store ────────────────────────────────────────


class TestMemoryStore:
    def test_save_and_list(self, tmp_path):
        from dcoder.memory.store import MemoryStore

        store = MemoryStore(project_root=tmp_path)
        store.save("test-key", "Test content")

        entries = store.list_all()
        assert len(entries) == 1
        assert entries[0].key == "test-key"
        assert entries[0].content == "Test content"
        assert entries[0].source == "project"

    def test_precedence_project_over_user(self, tmp_path):
        from dcoder.memory.store import MemoryStore

        user_home = tmp_path / "user"
        user_home.mkdir()
        project_root = tmp_path / "project"
        project_root.mkdir()

        store = MemoryStore(project_root=project_root, user_home=user_home)

        # Save to user scope
        store.save("shared-key", "User version", scope="user")
        # Save to project scope (should override)
        store.save("shared-key", "Project version", scope="project")

        entry = store.get("shared-key")
        assert entry is not None
        assert entry.content == "Project version"
        assert entry.source == "project"

    def test_load_context(self, tmp_path):
        from dcoder.memory.store import MemoryStore

        store = MemoryStore(project_root=tmp_path)
        store.save("pref-1", "Always use terraform fmt")
        store.save("pref-2", "Prefer Python 3.12+")

        context = store.load_context()
        assert "Persisted Memories" in context
        assert "terraform fmt" in context
        assert "Python 3.12" in context

    def test_delete(self, tmp_path):
        from dcoder.memory.store import MemoryStore

        store = MemoryStore(project_root=tmp_path)
        store.save("to-delete", "Temporary")
        assert store.delete("to-delete")
        assert store.get("to-delete") is None


# ── Skill Invocation Envelope ───────────────────────────


class TestSkillInvocationEnvelope:
    def test_build_envelope(self):
        from dcoder.skills.invocation import build_skill_invocation_envelope

        skill = {"name": "web-research", "description": "Search the web", "source": "built-in"}
        content = "# Web Research\nSearch for information."

        envelope = build_skill_invocation_envelope(skill, content, args="find CVEs")
        assert "web-research" in envelope.prompt
        assert "find CVEs" in envelope.prompt
        assert envelope.message_kwargs["additional_kwargs"]["__skill"]["name"] == "web-research"

    def test_build_envelope_no_args(self):
        from dcoder.skills.invocation import build_skill_invocation_envelope

        skill = {"name": "remember"}
        content = "# Remember\nExtract learnings."

        envelope = build_skill_invocation_envelope(skill, content)
        assert "remember" in envelope.prompt
        assert "User request" not in envelope.prompt
