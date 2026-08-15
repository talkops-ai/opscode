"""Unit tests for Phase 2 TUI Command & Input System modules:
- chat_input.py
- autocomplete.py
- app.py
"""

import pytest
from unittest.mock import Mock, MagicMock

from opscode.ui.widgets.autocomplete import AutocompletePopup
from opscode.ui.widgets.chat_input import ChatInput
from opscode.ui.command_registry import get_command


def test_chat_input_history():
    """Verify history navigation in ChatInput."""
    chat = ChatInput()
    chat._history = ["prompt 1", "prompt 2"]

    chat.action_history_prev()
    assert chat.text == "prompt 2"

    chat.action_history_prev()
    assert chat.text == "prompt 1"

    chat.action_history_next()
    assert chat.text == "prompt 2"


def test_chat_input_paste_collapse():
    """Verify multi-line paste collapsing."""
    class FakePasteEvent:
        text = "\n".join([f"line {i}" for i in range(10)])
        def prevent_default(self): pass
        def stop(self): pass

    chat = ChatInput()
    chat.on_paste(FakePasteEvent())

    assert "[Pasted 10 lines" in chat.text
    assert chat._pasted_full_text is not None


@pytest.mark.asyncio
async def test_chat_input_key_forwarding_to_approval():
    """Verify keys are forwarded to active _pending_approval_widget."""
    chat = ChatInput()
    mock_app = MagicMock()
    mock_menu = MagicMock()
    mock_menu.is_mounted = True
    mock_menu.display = True
    mock_menu._reason_input_active = False

    mock_app._pending_approval_widget = mock_menu
    chat._app = mock_app

    # Test key "y" forwards to action_select_approve
    key_event_y = Mock(key="y")
    res_y = await chat._handle_key_event(key_event_y)
    assert res_y is True
    key_event_y.prevent_default.assert_called_once()
    key_event_y.stop.assert_called_once()
    mock_menu.action_select_approve.assert_called_once()

    # Test key "a" forwards to action_select_auto
    key_event_a = Mock(key="a")
    res_a = await chat._handle_key_event(key_event_a)
    assert res_a is True
    mock_menu.action_select_auto.assert_called_once()

    # Test key "n" forwards to action_select_reject
    key_event_n = Mock(key="n")
    res_n = await chat._handle_key_event(key_event_n)
    assert res_n is True
    mock_menu.action_select_reject.assert_called_once()

    # Test key "1" forwards to action_select_position(0)
    key_event_1 = Mock(key="1")
    res_1 = await chat._handle_key_event(key_event_1)
    assert res_1 is True
    mock_menu.action_select_position.assert_called_once_with(0)


@pytest.mark.asyncio
async def test_chat_input_typing_suppression_during_approval():
    """Verify random typing keys are swallowed when approval is active and not in reason mode."""
    chat = ChatInput()
    mock_app = MagicMock()
    mock_menu = MagicMock()
    mock_menu.is_mounted = True
    mock_menu.display = True
    mock_menu._reason_input_active = False

    mock_app._pending_approval_widget = mock_menu
    chat._app = mock_app

    # Regular typing key like 'z'
    key_event_z = Mock(key="z")
    res_z = await chat._handle_key_event(key_event_z)
    assert res_z is True
    key_event_z.prevent_default.assert_called_once()
    key_event_z.stop.assert_called_once()
