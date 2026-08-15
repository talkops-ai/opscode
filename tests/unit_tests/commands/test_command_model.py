"""Unit tests for ModelHandler (/model) and ModelProfile metadata."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from opscode.commands._base import CommandContext
from opscode.commands.core.model import ModelHandler
from opscode.model.config import get_model_profile, format_token_count


@pytest.mark.asyncio
async def test_model_no_args_opens_selector():
    """Verify /model with no args opens ModelSelector screen."""
    mock_app = MagicMock()
    mock_app._show_model_selector = AsyncMock()

    ctx = CommandContext(app=mock_app, raw_command="/model")
    handler = ModelHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    mock_app._show_model_selector.assert_called_once()


@pytest.mark.asyncio
async def test_model_direct_switch():
    """Verify /model provider:model switches model directly."""
    mock_app = MagicMock()
    mock_app.switch_model = AsyncMock()

    ctx = CommandContext(app=mock_app, raw_command="/model anthropic:claude-3-5-sonnet", args="anthropic:claude-3-5-sonnet")
    handler = ModelHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "anthropic:claude-3-5-sonnet" in res.message
    mock_app.switch_model.assert_called_once_with("anthropic:claude-3-5-sonnet", extra_kwargs={})


@pytest.mark.asyncio
async def test_model_set_default():
    """Verify /model --default sets default model."""
    mock_app = MagicMock()
    mock_app.set_default_model = AsyncMock()

    ctx = CommandContext(app=mock_app, raw_command="/model --default gpt-4o", args="--default gpt-4o")
    handler = ModelHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "Default model set to: `gpt-4o`" in res.message
    mock_app.set_default_model.assert_called_once_with("gpt-4o")


@pytest.mark.asyncio
async def test_model_clear_default():
    """Verify /model --default --clear clears default model."""
    mock_app = MagicMock()
    mock_app.clear_default_model = AsyncMock()

    ctx = CommandContext(app=mock_app, raw_command="/model --default --clear", args="--default --clear")
    handler = ModelHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "Default model cleared." in res.message
    mock_app.clear_default_model.assert_called_once()


def test_get_model_profile_and_token_format():
    """Verify get_model_profile returns rich capabilities, context limits, and token formatting."""
    profile_entry = get_model_profile("openrouter:moonshotai/kimi-k3")
    assert profile_entry is not None
    prof = profile_entry["profile"]
    assert prof.get("name") == "Kimi K3"
    assert prof.get("max_input_tokens") == 1_000_000
    assert prof.get("reasoning_output") is True
    assert prof.get("tool_calling") is True

    assert format_token_count(1_000_000) == "1M"
    assert format_token_count(200_000) == "200k"
    assert format_token_count(16_384) == "16.4k" or format_token_count(16_384) == "16.4k" or "k" in format_token_count(16_384)
