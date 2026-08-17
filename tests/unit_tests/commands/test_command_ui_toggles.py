"""Unit tests for UI toggle handlers (/scrollbar, /timestamps, /notifications)."""

from unittest.mock import MagicMock

import pytest

from opscode.commands._base import CommandContext
from opscode.commands.power.ui_toggles import NotificationsHandler, ScrollbarHandler, TimestampsHandler


@pytest.mark.asyncio
async def test_scrollbar_handler_no_app():
    """Verify ScrollbarHandler gracefully handles None app."""
    ctx = CommandContext(app=None, raw_command="/scrollbar")
    handler = ScrollbarHandler()
    res = await handler.execute(ctx)
    assert res.success is True
    assert res.notify is not None and "scrollbar" in res.notify.lower()


@pytest.mark.asyncio
async def test_scrollbar_handler_with_messages_widget():
    """Verify ScrollbarHandler toggles vertical scrollbar size on MessageList."""
    mock_app = MagicMock()
    mock_messages = MagicMock()
    mock_messages.styles.scrollbar_size_vertical = 1
    mock_app.query_one.return_value = mock_messages

    ctx = CommandContext(app=mock_app, raw_command="/scrollbar")
    handler = ScrollbarHandler()
    res = await handler.execute(ctx)

    assert res.success is True
    assert mock_messages.styles.scrollbar_size_vertical == 0
    assert res.notify is not None and "hidden" in res.notify.lower()


@pytest.mark.asyncio
async def test_timestamps_handler_toggle_timestamps_method():
    """Verify TimestampsHandler calls toggle_timestamps on app."""
    mock_app = MagicMock()
    mock_app.toggle_timestamps.return_value = True

    ctx = CommandContext(app=mock_app, raw_command="/timestamps")
    handler = TimestampsHandler()
    res = await handler.execute(ctx)

    assert res.success is True
    assert res.notify is not None and "timestamps shown" in res.notify.lower()


@pytest.mark.asyncio
async def test_timestamps_handler_fallback_flag():
    """Verify TimestampsHandler toggles _message_timestamps_visible flag fallback."""
    mock_app = MagicMock(spec=["_message_timestamps_visible"])
    mock_app._message_timestamps_visible = True

    ctx = CommandContext(app=mock_app, raw_command="/timestamps")
    handler = TimestampsHandler()
    res = await handler.execute(ctx)

    assert res.success is True
    assert mock_app._message_timestamps_visible is False
    assert res.notify is not None and "timestamps hidden" in res.notify.lower()


@pytest.mark.asyncio
async def test_notifications_handler_no_app():
    """Verify NotificationsHandler handles None app gracefully."""
    ctx = CommandContext(app=None, raw_command="/notifications")
    handler = NotificationsHandler()
    res = await handler.execute(ctx)
    assert res.success is True
    assert res.notify is not None and "notification settings" in res.notify.lower()


@pytest.mark.asyncio
async def test_notifications_handler_with_app():
    """Verify NotificationsHandler pushes NotificationSettingsScreen on app."""
    mock_app = MagicMock()

    ctx = CommandContext(app=mock_app, raw_command="/notifications")
    handler = NotificationsHandler()
    res = await handler.execute(ctx)

    assert res.success is True
    mock_app.push_screen.assert_called_once()
