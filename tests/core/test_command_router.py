"""Unit tests for CommandRouter registration, discovery, and dispatching."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from dcoder.commands._base import BaseCommandHandler, CommandContext, CommandResult
from dcoder.commands._router import CommandRouter
from dcoder.commands._types import CommandCategory, SafetyLevel


class SampleCommand(BaseCommandHandler):
    @property
    def name(self) -> str:
        return "/sample"

    @property
    def aliases(self) -> tuple[str, ...]:
        return ("/s",)

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.CORE

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.READ_ONLY

    def validate(self, ctx: CommandContext) -> str | None:
        if ctx.args == "invalid":
            return "Invalid argument supplied"
        return None

    async def execute(self, ctx: CommandContext) -> CommandResult:
        if ctx.args == "error":
            raise RuntimeError("Internal execution crash")
        return CommandResult(success=True, message=f"Sample output: {ctx.args}")


class HighRiskSampleCommand(BaseCommandHandler):
    @property
    def name(self) -> str:
        return "/danger"

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.DEVOPS

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.HIGH_RISK

    async def execute(self, ctx: CommandContext) -> CommandResult:
        return CommandResult(success=True, message="Danger executed")


@pytest.fixture
def router():
    r = CommandRouter()
    r.register(SampleCommand())
    r.register(HighRiskSampleCommand())
    return r


@pytest.mark.asyncio
async def test_router_registration_and_lookup(router):
    """Verify lookup by canonical name and alias."""
    assert router.get_handler("/sample") is not None
    assert router.get_handler("/s") is not None
    assert router.get_handler("/SAMPLE") is not None
    assert router.get_handler("/nonexistent") is None


@pytest.mark.asyncio
async def test_router_dispatch_success(router):
    """Verify dispatch returns success result."""
    ctx = CommandContext(app=None, raw_command="/sample test", args="test")
    res = await router.dispatch("/sample test", ctx)
    assert res.success is True
    assert res.message == "Sample output: test"


@pytest.mark.asyncio
async def test_router_dispatch_alias(router):
    """Verify dispatch works via alias."""
    ctx = CommandContext(app=None, raw_command="/s foo", args="foo")
    res = await router.dispatch("/s foo", ctx)
    assert res.success is True
    assert res.message == "Sample output: foo"


@pytest.mark.asyncio
async def test_router_unknown_command(router):
    """Verify dispatch for unknown command returns error result."""
    ctx = CommandContext(app=None, raw_command="/unknown")
    res = await router.dispatch("/unknown", ctx)
    assert res.success is False
    assert "Unknown command" in (res.message or "")


@pytest.mark.asyncio
async def test_router_empty_command_dispatch(router):
    """Verify dispatching empty string returns failure."""
    ctx = CommandContext(app=None, raw_command="")
    res = await router.dispatch("   ", ctx)
    assert res.success is False
    assert res.message == "Empty command."


@pytest.mark.asyncio
async def test_router_validation_failure(router):
    """Verify pre-execution validation error stops execution."""
    ctx = CommandContext(app=None, raw_command="/sample invalid", args="invalid")
    res = await router.dispatch("/sample invalid", ctx)
    assert res.success is False
    assert res.message == "Invalid argument supplied"


@pytest.mark.asyncio
async def test_router_execution_exception_handling(router):
    """Verify runtime exception in handler is cleanly caught."""
    ctx = CommandContext(app=None, raw_command="/sample error", args="error")
    res = await router.dispatch("/sample error", ctx)
    assert res.success is False
    assert "Command failed: RuntimeError: Internal execution crash" in (res.message or "")


@pytest.mark.asyncio
async def test_router_high_risk_safety_gate_cancelled(router):
    """Verify HIGH_RISK command cancellation via safety gate."""
    mock_app = MagicMock()
    mock_decision = MagicMock()
    mock_decision.approved = False
    mock_app.push_screen_wait = AsyncMock(return_value=mock_decision)

    ctx = CommandContext(app=mock_app, raw_command="/danger")
    res = await router.dispatch("/danger", ctx)
    assert res.success is False
    assert res.message == "Cancelled by user."


def test_router_auto_discover_idempotent():
    """Verify auto_discover executes idempotently."""
    r = CommandRouter()
    r.auto_discover()
    assert r._discovered is True
    r.auto_discover()
    assert r._discovered is True


def test_router_all_handlers_property(router):
    """Verify all_handlers property returns a shallow copy of registered handlers."""
    handlers = router.all_handlers
    assert "/sample" in handlers
    assert "/danger" in handlers
    assert len(handlers) >= 3  # canonical names + aliases
