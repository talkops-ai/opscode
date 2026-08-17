"""Unit tests for safety guards and HITL confirmation."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from opscode.commands._base import BaseCommandHandler, CommandContext, CommandResult
from opscode.commands._guards import require_confirmation
from opscode.commands._router import CommandRouter
from opscode.commands._types import CommandCategory, SafetyLevel


class HighRiskCommand(BaseCommandHandler):
    @property
    def name(self) -> str:
        return "/highrisk"

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.DEVOPS

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.HIGH_RISK

    async def execute(self, ctx: CommandContext) -> CommandResult:
        return CommandResult(success=True, message="High risk executed")


class DestructiveCommand(BaseCommandHandler):
    @property
    def name(self) -> str:
        return "/destructive"

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.DEVOPS

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.DESTRUCTIVE

    async def execute(self, ctx: CommandContext) -> CommandResult:
        return CommandResult(success=True, message="Destructive executed")


@pytest.mark.asyncio
async def test_require_confirmation_read_only():
    """Verify READ_ONLY command bypasses confirmation popup."""
    handler = MagicMock()
    handler.safety_level = SafetyLevel.READ_ONLY
    ctx = CommandContext(app=None)
    assert await require_confirmation(handler, ctx) is True


class DummyDecision:
    def __init__(self, approved: bool):
        self.approved = approved


@pytest.mark.asyncio
async def test_high_risk_confirmation_approved():
    """Verify HIGH_RISK command proceeds when approved."""
    handler = HighRiskCommand()
    mock_app = MagicMock()
    mock_app.push_screen_wait = AsyncMock(return_value=DummyDecision(approved=True))

    ctx = CommandContext(app=mock_app, raw_command="/highrisk")
    router = CommandRouter()
    router.register(handler)

    res = await router.dispatch("/highrisk", ctx)
    assert res.success is True
    assert res.message == "High risk executed"


@pytest.mark.asyncio
async def test_destructive_confirmation_cancelled():
    """Verify DESTRUCTIVE command stops when cancelled."""
    handler = DestructiveCommand()
    mock_app = MagicMock()
    mock_app.push_screen_wait = AsyncMock(return_value=DummyDecision(approved=False))

    ctx = CommandContext(app=mock_app, raw_command="/destructive")
    router = CommandRouter()
    router.register(handler)

    res = await router.dispatch("/destructive", ctx)
    assert res.success is False
    assert res.message == "Cancelled by user."
