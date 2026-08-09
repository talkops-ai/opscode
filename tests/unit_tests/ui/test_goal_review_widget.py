"""Unit tests for GoalReviewMenu widget and flows."""

import asyncio
import pytest
from dcoder.ui.widgets.goal_review import (
    GoalReviewMenu,
    GoalReviewAccepted,
    GoalReviewEdited,
    GoalReviewRejected,
    GoalReviewCancelled,
)


@pytest.mark.asyncio
async def test_goal_review_menu_initialization():
    """Test GoalReviewMenu initialization and option setup."""
    menu = GoalReviewMenu(
        objective="Build feature X",
        criteria="- Step 1\n- Step 2",
    )
    assert menu._objective == "Build feature X"
    assert menu._criteria == "- Step 1\n- Step 2"
    assert menu._amendment is False
    assert menu._selected == 0


@pytest.mark.asyncio
async def test_goal_review_menu_accept():
    """Test GoalReviewMenu accept action."""
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    menu = GoalReviewMenu(
        objective="Build feature X",
        criteria="- Step 1\n- Step 2",
    )
    menu.set_future(future)
    menu.action_accept()

    assert future.done()
    result = future.result()
    assert result["type"] == "accepted"


@pytest.mark.asyncio
async def test_goal_review_menu_edit_submission():
    """Test GoalReviewMenu inline criteria editing submission."""
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    menu = GoalReviewMenu(
        objective="Build feature X",
        criteria="- Original criteria",
    )
    menu.set_future(future)

    # Trigger edit mode
    menu.action_edit()
    assert menu._input_mode == "edit"

    # Simulate revised criteria submission
    menu._edit_input.text = "- Revised criteria line 1\n- Revised criteria line 2"
    menu._submit_edit()

    assert future.done()
    result = future.result()
    assert result["type"] == "edited"
    assert result["criteria"] == "- Revised criteria line 1\n- Revised criteria line 2"


@pytest.mark.asyncio
async def test_goal_review_menu_rejection_with_message():
    """Test GoalReviewMenu rejection feedback submission."""
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    menu = GoalReviewMenu(
        objective="Build feature X",
        criteria="- Bad criteria",
    )
    menu.set_future(future)

    # Trigger rejection mode
    menu.action_reject_with_message()
    assert menu._input_mode == "reject"

    # Simulate user feedback
    menu._edit_input.text = "Please focus more on security requirements."
    menu._submit_rejection()

    assert future.done()
    result = future.result()
    assert result["type"] == "rejected"
    assert result["message"] == "Please focus more on security requirements."


@pytest.mark.asyncio
async def test_goal_review_menu_cancel():
    """Test GoalReviewMenu cancellation."""
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    menu = GoalReviewMenu(
        objective="Build feature X",
        criteria="- Step 1",
    )
    menu.set_future(future)
    menu.action_cancel()

    assert future.done()
    result = future.result()
    assert result["type"] == "cancelled"


@pytest.mark.asyncio
async def test_inline_prompt_text_area_newline_shortcuts():
    """Test multi-line newline insertion via shift+enter, ctrl+j, and backslash-enter."""
    from dcoder.ui._inline_prompt import InlinePromptTextArea
    from textual.events import Key

    text_area = InlinePromptTextArea()

    # shift+enter inserts newline
    event_shift = Key("enter", "enter")
    event_shift.key = "shift+enter"
    await text_area._on_key(event_shift)
    assert "\n" in text_area.text

    # ctrl+j inserts newline
    text_area.text = ""
    event_ctrl_j = Key("j", "j")
    event_ctrl_j.key = "ctrl+j"
    await text_area._on_key(event_ctrl_j)
    assert "\n" in text_area.text

    # Backslash followed by Enter inserts newline
    text_area.text = "Hello\\"
    text_area.move_cursor((0, 6))
    import time
    text_area._backslash_pending_time = time.monotonic()
    event_enter = Key("enter", "\r")
    await text_area._on_key(event_enter)
    assert "\n" in text_area.text


@pytest.mark.asyncio
async def test_goal_review_text_area_option_return_macos():
    """Test macOS Option+Return escape sequence handling in GoalReviewTextArea."""
    from dcoder.ui.widgets.goal_review import GoalReviewTextArea
    from textual.events import Key
    import time

    editor = GoalReviewTextArea()
    editor.text = "Line 1"

    # Simulate escape key event arriving first
    esc_event = Key("escape", "\x1b")
    await editor._on_key(esc_event)
    assert editor._escape_pending_time is not None

    # Simulate enter key event arriving 5ms later
    enter_event = Key("enter", "\r")
    await editor._on_key(enter_event)

    assert "\n" in editor.text
    assert editor._escape_pending_time is None


@pytest.mark.asyncio
async def test_goal_review_menu_cancel_cooloff():
    """Test that action_select is ignored during cool-off window after exiting input mode."""
    import time
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    menu = GoalReviewMenu(
        objective="Build feature X",
        criteria="- Original criteria",
    )
    menu.set_future(future)

    # Enter edit mode and then cancel
    menu.action_edit()
    assert menu._input_mode == "edit"
    menu.action_cancel()
    assert menu._input_mode is None

    # Trigger action_select immediately (within 150ms cooloff)
    menu.action_select()
    assert not future.done()  # Option 1 was NOT executed during cool-off


@pytest.mark.asyncio
async def test_textual_patch_xterm_parser_alt_enter():
    """Test that XTermParser patch preserves alt modifier on ESC + Return sequence."""
    from textual._xterm_parser import XTermParser
    import dcoder._textual_patches  # noqa: F401

    parser = XTermParser()
    events = list(parser._sequence_to_key_events("\x1b\r"))
    assert len(events) == 1
    assert events[0].key == "alt+enter"


@pytest.mark.asyncio
async def test_goal_review_text_area_standalone_escape_flushes():
    """Test that standalone Escape key in GoalReviewTextArea clears pending state on flush."""
    from dcoder.ui.widgets.goal_review import GoalReviewTextArea
    from textual.events import Key

    editor = GoalReviewTextArea()
    esc_event = Key("escape", "\x1b")
    await editor._on_key(esc_event)
    assert editor._escape_pending_time is not None

    # Trigger timer flush
    editor._flush_pending_escape()
    assert editor._escape_pending_time is None


@pytest.mark.asyncio
async def test_app_focus_restoration_on_rubric_evaluation_end(monkeypatch):
    """Test that _handle_rubric_evaluation_end updates state status and triggers focus restoration."""
    from dcoder.ui.app import DCoderApp
    from dcoder.commands.power.goal import get_goal_state

    app = DCoderApp()
    state = get_goal_state(app)
    state.objective = "Test objective"

    focus_called = False

    def mock_focus():
        nonlocal focus_called
        focus_called = True

    monkeypatch.setattr(app, "_focus_chat_input_after_refresh", mock_focus)

    app._handle_rubric_evaluation_end({"type": "rubric_evaluation_end", "result": "satisfied"})
    assert state.status == "complete"
    assert focus_called is True


@pytest.mark.asyncio
async def test_app_focus_restoration_on_adhoc_rubric_evaluation_end(monkeypatch):
    """Test that _handle_rubric_evaluation_end clears next_rubric and triggers focus restoration even without a goal objective."""
    from dcoder.ui.app import DCoderApp
    from dcoder.commands.power.goal import get_goal_state

    app = DCoderApp()
    state = get_goal_state(app)
    state.objective = None
    state.next_rubric = "One turn criteria"

    focus_called = False

    def mock_focus():
        nonlocal focus_called
        focus_called = True

    monkeypatch.setattr(app, "_focus_chat_input_after_refresh", mock_focus)

    app._handle_rubric_evaluation_end({"type": "rubric_evaluation_end", "result": "satisfied"})
    assert state.next_rubric is None
    assert focus_called is True

