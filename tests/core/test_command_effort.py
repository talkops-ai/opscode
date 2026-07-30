"""Unit tests for EffortHandler (/effort)."""

from unittest.mock import MagicMock

import pytest

from dcoder.commands._base import CommandContext
from dcoder.commands.core.effort import EffortHandler


@pytest.mark.asyncio
async def test_effort_no_args_displays_current():
    """Verify /effort with no args shows current effort."""
    mock_settings = MagicMock()
    mock_settings.reasoning_effort = "medium"
    mock_settings.model_name = "claude-3-5-sonnet"

    ctx = CommandContext(app=None, settings=mock_settings, raw_command="/effort")
    handler = EffortHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert "medium" in res.message


@pytest.mark.asyncio
async def test_effort_set_valid_level():
    """Verify /effort sets valid reasoning effort level."""
    mock_settings = MagicMock()

    ctx = CommandContext(app=None, settings=mock_settings, raw_command="/effort high", args="high")
    handler = EffortHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert mock_settings.reasoning_effort == "high"


@pytest.mark.asyncio
async def test_effort_reject_invalid_level():
    """Verify /effort rejects unsupported level."""
    mock_settings = MagicMock()

    ctx = CommandContext(app=None, settings=mock_settings, raw_command="/effort ultra", args="ultra")
    handler = EffortHandler()

    res = await handler.execute(ctx)
    assert res.success is False
    assert "Unknown effort level" in res.message


@pytest.mark.asyncio
async def test_effort_clear_resets():
    """Verify /effort clear resets reasoning effort to None."""
    mock_settings = MagicMock()
    mock_settings.reasoning_effort = "high"

    ctx = CommandContext(app=None, settings=mock_settings, raw_command="/effort clear", args="clear")
    handler = EffortHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert mock_settings.reasoning_effort is None
