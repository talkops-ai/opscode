"""Shared fixtures for unit tests.

Provides a properly-configured mock_app fixture (Option C), deterministic
fakes (models, backends, checkpointers) and reusable factory helpers so
individual test modules stay DRY.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from dcoder.commands._base import CommandContext, CommandResult


from dcoder.commands.power.goal import GoalState


# ── Mock app fixture (Option C) ─────────────────────────────────────


@pytest.fixture
def mock_app():
    """Properly-configured mock app that satisfies all command/middleware interfaces."""
    app = MagicMock()

    # ── Goal/rubric mutation boundary (async context manager) ──
    @asynccontextmanager
    async def _noop_boundary():
        yield

    app._goal_state = GoalState()
    app._goal_state_mutation_boundary = _noop_boundary

    app._run_goal_criteria_request = AsyncMock()
    app._persist_goal_rubric_state = AsyncMock()

    # ── Thread / session state ──
    app._agent_thread_id = "test-thread-001"
    app._resume_thread = None
    app._session_state = None
    app._agent_running = False

    # ── UI stubs ──
    app._pending_messages = []
    app._queued_widgets = []
    app._sync_status_queued = MagicMock()
    app._force_interrupt_active_work = MagicMock()
    app._chat_input = None
    app._context_tokens = 0
    app._adapter = None
    app._model = None
    app._reasoning_effort = None
    app._message_timestamps_visible = False
    app._discovered_plugins = []

    # ── Async methods used by commands ──
    app._show_model_selector = AsyncMock()
    app.switch_model = AsyncMock()
    app._switch_model = AsyncMock()
    app._show_effort_selector = AsyncMock()
    app._show_thread_selector = AsyncMock()
    app._switch_thread = AsyncMock()
    app._load_thread_history = AsyncMock()
    app._get_conversation_token_count = AsyncMock(return_value=0)
    app._handle_mcp_reconnect_command = AsyncMock()
    app._set_effort_override = MagicMock(return_value=None)
    app._handle_skill_command = AsyncMock()

    # ── Sync methods ──
    app._show_agent_selector = MagicMock()
    app._open_skills_viewer = MagicMock()
    app._show_plugin_manager = MagicMock()
    app._start_mcp_login = MagicMock()
    app._discover_skills = MagicMock()
    app._discover_plugins = MagicMock()
    app.reload_css = MagicMock()
    app.get_discovered_skills = MagicMock(return_value=[])

    # ── Permission store ──
    app._permission_store = MagicMock()

    return app


# ── Command helpers ─────────────────────────────────────────────────


@pytest.fixture
def make_ctx(mock_app):
    """Factory fixture that builds a minimal CommandContext.

    Defaults to using the shared ``mock_app`` fixture. Pass ``app=``
    to override with your own.

    Usage::

        def test_foo(make_ctx):
            ctx = make_ctx(args="show", raw="/goal show")
    """

    def _factory(
        *,
        args: str = "",
        raw: str = "",
        app: object | None = None,
        model_spec: str | None = None,
    ) -> CommandContext:
        return CommandContext(
            app=app if app is not None else mock_app,
            raw_command=raw or f"/test {args}".strip(),
            args=args,
            model_spec=model_spec,
        )

    return _factory


# ── Mock backend / runtime ──────────────────────────────────────────


@pytest.fixture
def mock_backend():
    """Pre-wired MagicMock backend with configurable `.execute()` return.

    The mock_backend.execute returns a MagicMock with output="" and exit_code=0
    by default. Override in your test as needed:

        mock_backend.execute.return_value.output = "custom output"
    """
    backend = MagicMock()
    mock_res = MagicMock()
    mock_res.output = ""
    mock_res.exit_code = 0
    backend.execute.return_value = mock_res
    return backend


@pytest.fixture
def mock_runtime(mock_backend):
    """MagicMock tool runtime with mock_backend wired in."""
    try:
        from langchain.tools import ToolRuntime
        runtime = MagicMock(spec=ToolRuntime)
    except ImportError:
        runtime = MagicMock()
    runtime.backend = mock_backend
    return runtime


# ── Project root fixture ────────────────────────────────────────────


@pytest.fixture
def tmp_project_root(tmp_path):
    """Temporary project root pre-populated with `.dcoder/` structure."""
    dcoder_dir = tmp_path / ".dcoder"
    dcoder_dir.mkdir()
    (dcoder_dir / "memory").mkdir()
    (dcoder_dir / "skills").mkdir()
    return tmp_path


# ── Source root fixture ─────────────────────────────────────────────


@pytest.fixture
def src_root():
    """Path to the dcoder source root (repo root)."""
    from pathlib import Path
    return Path(__file__).parent.parent.parent
