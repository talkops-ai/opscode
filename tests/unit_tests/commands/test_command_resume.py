"""Unit tests for ResumeHandler (/resume, /threads)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from dcoder.commands._base import CommandContext
from dcoder.commands.core.resume import ResumeHandler


@pytest.mark.asyncio
async def test_resume_no_args_opens_selector():
    """Verify /resume with no args opens ThreadSelector."""
    mock_app = MagicMock()
    mock_app._show_thread_selector = AsyncMock()

    ctx = CommandContext(app=mock_app, raw_command="/resume")
    handler = ResumeHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    mock_app._show_thread_selector.assert_called_once()


@pytest.mark.asyncio
async def test_resume_latest_thread():
    """Verify /resume -r resumes most recent thread."""
    mock_app = MagicMock()
    mock_app.get_recent_threads = AsyncMock(return_value=["thread-latest-123"])
    mock_app.resume_thread = AsyncMock()

    ctx = CommandContext(app=mock_app, raw_command="/resume -r", args="-r")
    handler = ResumeHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "thread-latest-123" in res.message
    mock_app.resume_thread.assert_called_once_with("thread-latest-123")


@pytest.mark.asyncio
async def test_resume_specific_thread():
    """Verify /resume -r <ID> resumes specific thread by ID."""
    mock_app = MagicMock()
    mock_app.resume_thread = AsyncMock()

    ctx = CommandContext(app=mock_app, raw_command="/resume -r thread-abc", args="-r thread-abc")
    handler = ResumeHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "thread-abc" in res.message
    mock_app.resume_thread.assert_called_once_with("thread-abc")


@pytest.mark.asyncio
async def test_resume_nonexistent_thread():
    """Verify /resume -r fails when thread does not exist."""
    mock_session = MagicMock()
    mock_session.thread_exists = AsyncMock(return_value=False)

    ctx = CommandContext(app=MagicMock(), session=mock_session, raw_command="/resume -r invalid-id", args="-r invalid-id")
    handler = ResumeHandler()

    res = await handler.execute(ctx)
    assert res.success is False
    assert res.message is not None and "Thread not found" in res.message


@pytest.mark.asyncio
async def test_app_show_thread_selector():
    """Verify DCoderApp._show_thread_selector instantiates and pushes ThreadSelectorScreen."""
    from dcoder.ui.app import DCoderApp
    from dcoder.ui.widgets.thread_selector import ThreadSelectorScreen

    app = DCoderApp()
    app.push_screen = MagicMock()

    await app._show_thread_selector()

    app.push_screen.assert_called_once()
    screen_arg = app.push_screen.call_args[0][0]
    assert isinstance(screen_arg, ThreadSelectorScreen)


@pytest.mark.asyncio
async def test_thread_selector_screen_delete():
    """Verify ThreadSelectorScreen action_delete_thread triggers deletion worker."""
    from dcoder.ui.widgets.thread_selector import ThreadSelectorScreen

    threads = [{"thread_id": "test-thread-1", "message_count": 5, "initial_prompt": "hello"}]
    screen = ThreadSelectorScreen(threads=threads)
    screen._delete_thread_async = MagicMock(return_value=None)
    screen.run_worker = MagicMock()

    mock_opt_list = MagicMock()
    mock_opt = MagicMock()
    mock_opt.id = "test-thread-1"
    mock_opt_list.highlighted = 1
    mock_opt_list.get_option_at_index.return_value = mock_opt
    screen.query_one = MagicMock(return_value=mock_opt_list)

    screen.action_delete_thread()
    screen.run_worker.assert_called_once()


