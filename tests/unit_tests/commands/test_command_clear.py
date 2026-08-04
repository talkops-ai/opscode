"""Unit tests for ClearHandler (/clear) and ForceClearHandler (/force-clear)."""

from unittest.mock import MagicMock

import pytest

from dcoder.commands._base import CommandContext
from dcoder.commands.core.clear import ClearHandler, ForceClearHandler


@pytest.mark.asyncio
async def test_clear_handler_resets_thread():
    """Verify ClearHandler resets session thread ID and mounts message."""
    mock_app = MagicMock()
    mock_session = MagicMock()
    mock_session.reset_thread.return_value = "new-uuid-1234"
    mock_session.previous_thread_id = "old-uuid-5678"
    mock_app._session_state = mock_session

    ctx = CommandContext(app=mock_app, session=mock_session, raw_command="/clear")
    handler = ClearHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "Started new thread: `new-uuid-1234`" in res.message
    assert res.message is not None and "Previous thread: `old-uuid-5678`" in res.message


@pytest.mark.asyncio
async def test_force_clear_interrupts_work():
    """Verify ForceClearHandler invokes force_interrupt_active_work."""
    mock_app = MagicMock()
    ctx = CommandContext(app=mock_app, raw_command="/force-clear")
    handler = ForceClearHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    mock_app._force_interrupt_active_work.assert_called_once()
