"""Unit tests for HelpHandler (/help)."""

from unittest.mock import MagicMock

import pytest

from dcoder.commands._base import BaseCommandHandler, CommandContext, CommandResult
from dcoder.commands._router import CommandRouter
from dcoder.commands._types import CommandCategory, SafetyLevel
from dcoder.commands.core.help_cmd import HelpHandler


class SampleCoreCommand(BaseCommandHandler):
    @property
    def name(self) -> str:
        return "/testcore"

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.CORE

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.READ_ONLY

    async def execute(self, ctx: CommandContext) -> CommandResult:
        return CommandResult(success=True)


@pytest.mark.asyncio
async def test_general_help_returns_categorized_output():
    """Verify general /help shows categorized commands."""
    mock_app = MagicMock()
    router = CommandRouter()
    router.register(HelpHandler())
    router.register(SampleCoreCommand())
    mock_app._command_router = router

    ctx = CommandContext(app=mock_app, raw_command="/help")
    handler = HelpHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "Commands:" in res.message
    assert res.message is not None and "Interactive Features:  \n" in res.message
    assert res.message is not None and "Ctrl+X          Open prompt in external editor  \n" in res.message
    assert res.message is not None and "Ctrl+N          Review pending notifications  \n" in res.message


@pytest.mark.asyncio
async def test_specific_help_known_command():
    """Verify /help /testcore shows specific command details."""
    mock_app = MagicMock()
    router = CommandRouter()
    router.register(SampleCoreCommand())
    mock_app._command_router = router

    ctx = CommandContext(app=mock_app, raw_command="/help /testcore", args="/testcore")
    handler = HelpHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and res.message is not None and "**Command:** `/testcore`" in res.message
    assert res.message is not None and res.message is not None and "**Category:** Core" in res.message


@pytest.mark.asyncio
async def test_specific_help_unknown_command():
    """Verify /help /unknown returns failure result."""
    mock_app = MagicMock()
    router = CommandRouter()
    mock_app._command_router = router

    ctx = CommandContext(app=mock_app, raw_command="/help /unknown", args="/unknown")
    handler = HelpHandler()

    res = await handler.execute(ctx)
    assert res.success is False
    assert res.message is not None and res.message is not None and "Unknown command: `/unknown`" in res.message
