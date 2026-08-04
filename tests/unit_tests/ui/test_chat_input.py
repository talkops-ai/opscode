"""Unit tests for Phase 2 TUI Command & Input System modules:
- chat_input.py
- autocomplete.py
- app.py
"""

import pytest

from dcoder.ui.autocomplete import AutocompletePopup
from dcoder.ui.chat_input import ChatInput
from dcoder.ui.command_registry import get_command


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



