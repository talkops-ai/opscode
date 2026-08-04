"""Tests for the CommandRouter: registration, lookup, dispatch, and auto-discovery.

These tests verify the actual routing logic — the gateway for all slash commands.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from dcoder.commands._base import BaseCommandHandler, CommandContext, CommandResult
from dcoder.commands._router import CommandRouter
from dcoder.commands._types import CommandCategory, SafetyLevel


# ── Helper: concrete handler for tests ──────────────────────────────


class _StubHandler(BaseCommandHandler):
    """Minimal concrete handler for testing router mechanics."""

    def __init__(
        self,
        name: str = "/stub",
        aliases: tuple[str, ...] = (),
        category: CommandCategory = CommandCategory.CORE,
        safety: SafetyLevel = SafetyLevel.LOW_RISK,
        result: CommandResult | None = None,
    ):
        self._name = name
        self._aliases = aliases
        self._category = category
        self._safety = safety
        self._result = result or CommandResult(success=True, message="ok")

    @property
    def name(self) -> str:
        return self._name

    @property
    def aliases(self) -> tuple[str, ...]:
        return self._aliases

    @property
    def category(self) -> CommandCategory:
        return self._category

    @property
    def safety_level(self) -> SafetyLevel:
        return self._safety

    async def execute(self, ctx: CommandContext) -> CommandResult:
        return self._result


# ── Registration tests ──────────────────────────────────────────────


class TestCommandRouterRegistration:
    def test_register_by_name(self):
        """Handler is retrievable by its canonical name."""
        router = CommandRouter()
        handler = _StubHandler(name="/help")
        router.register(handler)
        assert router.get_handler("/help") is handler

    def test_register_with_aliases(self):
        """All aliases resolve to the same handler instance."""
        router = CommandRouter()
        handler = _StubHandler(name="/quit", aliases=("/q", "/exit"))
        router.register(handler)
        assert router.get_handler("/quit") is handler
        assert router.get_handler("/q") is handler
        assert router.get_handler("/exit") is handler

    def test_case_insensitive_lookup(self):
        """/Help and /HELP resolve the same as /help."""
        router = CommandRouter()
        handler = _StubHandler(name="/help")
        router.register(handler)
        assert router.get_handler("/Help") is handler
        assert router.get_handler("/HELP") is handler

    def test_unknown_command_returns_none(self):
        """Unregistered command → None."""
        router = CommandRouter()
        assert router.get_handler("/nonexistent") is None

    def test_prefix_match_for_skill(self):
        """``/skill:terraform`` matches handler registered as ``/skill:``."""
        router = CommandRouter()
        handler = _StubHandler(name="/skill:")
        router.register(handler)
        assert router.get_handler("/skill:terraform") is handler

    def test_all_handlers_returns_copy(self):
        """all_handlers returns a dict copy, not the internal dict."""
        router = CommandRouter()
        handler = _StubHandler(name="/test")
        router.register(handler)
        handlers = router.all_handlers
        handlers.clear()
        assert router.get_handler("/test") is handler  # internal unaffected


# ── Dispatch tests ──────────────────────────────────────────────────


class TestCommandRouterDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_empty_command(self, mock_app, make_ctx):
        """Empty string → failure result."""
        router = CommandRouter()
        ctx = make_ctx(raw="", args="")
        result = await router.dispatch("", ctx)
        assert not result.success
        assert result.message is not None and "Empty command" in result.message

    @pytest.mark.asyncio
    async def test_dispatch_unknown_command(self, mock_app, make_ctx):
        """Unknown command → failure with command name."""
        router = CommandRouter()
        ctx = make_ctx(raw="/nonexistent")
        result = await router.dispatch("/nonexistent", ctx)
        assert not result.success
        assert result.message is not None and "/nonexistent" in result.message

    @pytest.mark.asyncio
    async def test_dispatch_calls_handler(self, mock_app, make_ctx):
        """Known command → handler.execute() called, result forwarded."""
        router = CommandRouter()
        expected = CommandResult(success=True, message="executed")
        handler = _StubHandler(name="/test", result=expected)
        router.register(handler)
        ctx = make_ctx(raw="/test", args="")
        result = await router.dispatch("/test", ctx)
        assert result.success
        assert result.message == "executed"

    @pytest.mark.asyncio
    async def test_dispatch_handler_exception_returns_failure(self, mock_app, make_ctx):
        """If handler.execute() raises, dispatch returns a failure result."""
        router = CommandRouter()
        handler = _StubHandler(name="/boom")
        # Override execute to raise
        handler.execute = AsyncMock(side_effect=RuntimeError("kaboom"))
        router.register(handler)
        ctx = make_ctx(raw="/boom")
        result = await router.dispatch("/boom", ctx)
        assert not result.success
        assert result.message is not None and "kaboom" in result.message

    @pytest.mark.asyncio
    async def test_dispatch_validates_before_execute(self, mock_app, make_ctx):
        """If handler.validate() returns an error, execute() is not called."""
        router = CommandRouter()
        handler = _StubHandler(name="/invalid")
        handler.validate = lambda ctx: "args required"
        handler.execute = AsyncMock()
        router.register(handler)
        ctx = make_ctx(raw="/invalid")
        result = await router.dispatch("/invalid", ctx)
        assert not result.success
        assert result.message is not None and "args required" in result.message
        handler.execute.assert_not_called()


# ── Auto-discovery tests ────────────────────────────────────────────


class TestCommandRouterAutoDiscovery:
    def test_discover_populates_handlers(self):
        """auto_discover() loads handlers from dcoder.commands sub-packages."""
        router = CommandRouter()
        router.auto_discover()
        handlers = router.all_handlers
        # Core commands that must exist
        assert router.get_handler("/help") is not None
        assert router.get_handler("/clear") is not None
        assert router.get_handler("/model") is not None

    def test_discover_idempotent(self):
        """Calling auto_discover() twice doesn't duplicate handlers."""
        router = CommandRouter()
        router.auto_discover()
        count1 = len(router.all_handlers)
        router.auto_discover()
        count2 = len(router.all_handlers)
        assert count1 == count2

    def test_discover_loads_power_commands(self):
        """Power commands (/goal, /rubric, /loop) are discovered."""
        router = CommandRouter()
        router.auto_discover()
        assert router.get_handler("/goal") is not None
        assert router.get_handler("/rubric") is not None

    def test_discover_loads_core_commands(self):
        """Core commands (/auth, /cost, /effort, /config) discovered."""
        router = CommandRouter()
        router.auto_discover()
        for cmd in ["/auth", "/cost", "/effort", "/config", "/compact"]:
            assert router.get_handler(cmd) is not None, f"{cmd} not discovered"
