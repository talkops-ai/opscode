"""Unit tests for ExitHandler (/exit, /quit, /q)."""

from unittest.mock import MagicMock

import pytest

from dcoder.commands._base import CommandContext
from dcoder.commands._types import BypassTier, CommandCategory, SafetyLevel
from dcoder.commands.core.exit_cmd import ExitHandler


@pytest.mark.asyncio
async def test_exit_handler_metadata():
    """Verify ExitHandler properties."""
    handler = ExitHandler()
    assert handler.name == "/exit"
    assert handler.aliases == ("/quit", "/q")
    assert handler.category == CommandCategory.CORE
    assert handler.safety_level == SafetyLevel.READ_ONLY
    assert handler.bypass_tier == BypassTier.ALWAYS


@pytest.mark.asyncio
async def test_exit_handler_executes_app_exit():
    """Verify ExitHandler calls app.exit()."""
    mock_app = MagicMock()
    ctx = CommandContext(app=mock_app, raw_command="/exit")
    handler = ExitHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.mount_as_app_message is False
    mock_app.exit.assert_called_once()
