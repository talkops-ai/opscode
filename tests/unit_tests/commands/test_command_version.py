"""Unit tests for VersionHandler (/version)."""

from unittest.mock import MagicMock

import pytest

from opscode.commands._base import CommandContext
from opscode.commands.power.version import VersionHandler


@pytest.mark.asyncio
async def test_version_handler_output():
    """Verify /version displays version info."""
    mock_settings = MagicMock()
    mock_settings.model_name = "claude-3-5-sonnet"

    ctx = CommandContext(app=None, settings=mock_settings)
    handler = VersionHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and res.message is not None and "opscode-code version:" in res.message
    assert res.message is not None and res.message is not None and "Python version:" in res.message
    assert res.message is not None and "claude-3-5-sonnet" in res.message


@pytest.mark.asyncio
async def test_version_handler_fallback_to_app_model():
    """Verify /version falls back to app model when settings model_name is None."""
    mock_app = MagicMock()
    mock_app._model = "gpt-4o"

    ctx = CommandContext(app=mock_app, settings=None)
    handler = VersionHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and res.message is not None and "gpt-4o" in res.message
