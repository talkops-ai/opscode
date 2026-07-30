"""Unit tests for CopyHandler (/copy)."""

from unittest.mock import MagicMock

import pytest

from dcoder.commands._base import CommandContext
from dcoder.commands.power.copy import CopyHandler


@pytest.mark.asyncio
async def test_copy_no_assistant_message():
    """Verify /copy handles absence of assistant message."""
    mock_app = MagicMock()
    mock_app.get_latest_assistant_message.return_value = None

    ctx = CommandContext(app=mock_app, raw_command="/copy")
    handler = CopyHandler()

    res = await handler.execute(ctx)
    assert res.success is False
    assert res.notify == "No assistant message content available to copy."


@pytest.mark.asyncio
async def test_copy_success_with_message():
    """Verify /copy retrieves assistant message content."""
    mock_app = MagicMock()
    mock_app.get_latest_assistant_message.return_value = "Hello assistant response"

    ctx = CommandContext(app=mock_app, raw_command="/copy")
    handler = CopyHandler()

    res = await handler.execute(ctx)
    assert res.notify == "Copied latest assistant message to clipboard." or "unavailable" in (res.notify or "")
