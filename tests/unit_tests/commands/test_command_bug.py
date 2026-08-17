"""Unit tests for BugHandler (/bug, /feedback)."""

from unittest.mock import MagicMock, patch

import pytest

from opscode.commands._base import CommandContext
from opscode.commands._router import CommandRouter
from opscode.commands.core.bug import BugHandler


@pytest.mark.asyncio
@patch("webbrowser.open")
async def test_bug_handler(mock_open):
    """Verify BugHandler opens issue tracker URL."""
    ctx = CommandContext(app=None, raw_command="/bug")
    handler = BugHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "https://github.com/talkops-ai/opscode/issues/new" in res.message
    mock_open.assert_called_once_with("https://github.com/talkops-ai/opscode/issues/new")


@pytest.mark.asyncio
@patch("webbrowser.open", side_effect=Exception("Browser not available"))
async def test_bug_handler_no_browser_fallback(mock_open):
    """Verify BugHandler handles browser open exception gracefully."""
    ctx = CommandContext(app=None, raw_command="/feedback")
    handler = BugHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "https://github.com/talkops-ai/opscode/issues/new" in res.message


@pytest.mark.asyncio
@patch("webbrowser.open")
async def test_feedback_alias_router_dispatch(mock_open):
    """Verify CommandRouter dispatches /feedback alias to BugHandler."""
    router = CommandRouter()
    router.register(BugHandler())
    mock_app = MagicMock()
    ctx = CommandContext(app=mock_app, raw_command="/feedback")

    res = await router.dispatch("/feedback", ctx)
    assert res.success is True
    assert res.message is not None and "https://github.com/talkops-ai/opscode/issues/new" in res.message
    mock_open.assert_called_once_with("https://github.com/talkops-ai/opscode/issues/new")
