"""Unit tests for FastHandler (/fast)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from dcoder.commands._base import CommandContext
from dcoder.commands.core.fast import FastHandler


@pytest.mark.asyncio
async def test_fast_toggle_on():
    """Verify /fast enables fast mode on first call."""
    mock_app = MagicMock()
    mock_app.switch_model = AsyncMock()
    mock_app.save_previous_model = MagicMock()

    mock_settings = MagicMock()
    mock_settings.fast_model = "claude-3-5-haiku"
    mock_settings.model_name = "claude-3-5-sonnet"
    mock_settings.reasoning_effort = "high"

    ctx = CommandContext(app=mock_app, settings=mock_settings, raw_command="/fast")
    handler = FastHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "Fast Mode ON" in res.message
    mock_app.save_previous_model.assert_called_once_with("claude-3-5-sonnet", "high")
    mock_app.switch_model.assert_called_once_with("claude-3-5-haiku")
    assert mock_settings.reasoning_effort == "low"


@pytest.mark.asyncio
async def test_fast_toggle_off():
    """Verify /fast restores previous model and effort on second call."""
    mock_app = MagicMock()
    mock_app.switch_model = AsyncMock()
    mock_app.get_previous_model.return_value = "claude-3-5-sonnet"
    mock_app.get_previous_effort.return_value = "high"

    mock_settings = MagicMock()
    mock_settings.fast_model = "claude-3-5-haiku"
    mock_settings.model_name = "claude-3-5-haiku"
    mock_settings.reasoning_effort = "low"

    ctx = CommandContext(app=mock_app, settings=mock_settings, raw_command="/fast")
    handler = FastHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "Fast Mode OFF" in res.message
    mock_app.switch_model.assert_called_once_with("claude-3-5-sonnet")
    assert mock_settings.reasoning_effort == "high"
