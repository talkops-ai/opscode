"""Unit tests for command framework base abstractions."""

import pytest

from opscode.commands._base import BaseCommandHandler, CommandContext, CommandResult
from opscode.commands._types import BypassTier, CommandCategory, SafetyLevel


def test_command_context_immutability():
    """Verify CommandContext is frozen and immutable."""
    ctx = CommandContext(app=None, raw_command="/test", args="hello")
    assert ctx.raw_command == "/test"
    assert ctx.args == "hello"

    with pytest.raises(AttributeError):
        ctx.args = "new_args"  # type: ignore


def test_command_result_defaults():
    """Verify default field values for CommandResult."""
    res = CommandResult(success=True)
    assert res.success is True
    assert res.message is None
    assert res.data == {}
    assert res.mount_as_app_message is True
    assert res.push_screen is None
    assert res.notify is None
    assert res.notify_severity == "information"


class DummyHandler(BaseCommandHandler):
    @property
    def name(self) -> str:
        return "/dummy"

    @property
    def aliases(self) -> tuple[str, ...]:
        return ("/d", "/dum")

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.CORE

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.READ_ONLY

    async def execute(self, ctx: CommandContext) -> CommandResult:
        return CommandResult(success=True, message=f"Executed with args: {ctx.args}")


@pytest.mark.asyncio
async def test_dummy_handler_execution():
    """Test standard subclass implementation of BaseCommandHandler."""
    handler = DummyHandler()
    assert handler.name == "/dummy"
    assert handler.aliases == ("/d", "/dum")
    assert handler.category == CommandCategory.CORE
    assert handler.safety_level == SafetyLevel.READ_ONLY
    assert handler.bypass_tier == BypassTier.QUEUED
    assert handler.validate(CommandContext(app=None)) is None

    ctx = CommandContext(app=None, raw_command="/dummy bar", args="bar")
    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message == "Executed with args: bar"
