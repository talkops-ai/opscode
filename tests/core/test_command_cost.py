"""Unit tests for CostHandler (/cost, /tokens)."""

from unittest.mock import MagicMock

import pytest

from dcoder.commands._base import CommandContext
from dcoder.commands.core.cost import CostHandler


def test_format_token_counts():
    """Verify static helper formatting."""
    assert CostHandler._format(500) == "500"
    assert CostHandler._format(1500) == "1.5k"
    assert CostHandler._format(2500000) == "2.5M"


@pytest.mark.asyncio
async def test_cost_handler_zero_tokens():
    """Verify /cost output when zero tokens used."""
    mock_app = MagicMock()
    mock_app._adapter.stats.input_tokens = 0
    mock_app._adapter.stats.output_tokens = 0

    ctx = CommandContext(app=mock_app, model_spec="claude-3-5-sonnet")
    handler = CostHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "No token usage yet" in res.message


@pytest.mark.asyncio
async def test_cost_handler_with_usage_and_limit():
    """Verify /cost formatting when tokens used with limit."""
    mock_app = MagicMock()
    mock_app._adapter.stats.input_tokens = 25000
    mock_app._adapter.stats.output_tokens = 7000

    mock_settings = MagicMock()
    mock_settings.model_name = "gpt-4o"
    mock_settings.model_context_limit = 128000

    ctx = CommandContext(app=mock_app, settings=mock_settings)
    handler = CostHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "32.0k / 128.0k tokens (25%)" in res.message
    assert res.message is not None and "gpt-4o" in res.message
