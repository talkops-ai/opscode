"""Chat input widget for DCoder TUI.

A multi-line text input area with input mode detection (normal/command/shell),
prompt history, paste collapse preview, slash-command autocomplete,
and mode-reactive prompt glyph (❯ / / / $) with visual feedback.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Literal, Self

from rich.cells import cell_len
from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.reactive import reactive
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Static, TextArea

from dcoder.ui.autocomplete import AutocompletePopup

logger = logging.getLogger(__name__)

# ── Input Mode Types ────────────────────────────────────

InputMode = Literal["normal", "command", "shell", "shell_incognito"]

MODE_PREFIXES: dict[str, str] = {
    "shell_incognito": "!!",
    "shell": "!",
    "command": "/",
}

MODE_DISPLAY_GLYPHS: dict[str, str] = {
    "normal": "❯",
    "command": "/",
    "shell": "$",
    "shell_incognito": "$",
}


def detect_input_mode(text: str) -> InputMode:
    """Detect the input mode from the first characters of *text*."""
    if text.startswith("!!"):
        return "shell_incognito"
    if text.startswith("!"):
        return "shell"
    if text.startswith("/"):
        return "command"
    return "normal"


# Dim style used for inline argument hint ghost text.
_HINT_STYLE = Style(color="grey50", italic=True)


class ChatTextArea(TextArea):
    """Internal TextArea for ChatInput widget.

    Extends Textual's ``TextArea`` with an inline **argument hint** rendered as
    dim ghost text after the cursor.  When the user types a known slash command
    followed by a space (e.g. ``/rubric ``), the ``argument_hint`` reactive is
    set to the command's hint string (e.g. ``[set|next|show|clear|…]``) and
    ``render_line`` appends a dimmed ``Strip`` so the hint appears inline.
    """

    argument_hint: reactive[str] = reactive("")
    """Ghost text shown after cursor when a slash command expects arguments."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            language=None,
            show_line_numbers=False,
            **kwargs,
        )

    def render_line(self, y: int) -> Strip:
        """Render a single line, appending argument hint ghost text at EOL.

        The hint is rendered on the *last* document line only, immediately
        after the user's typed text, in a dim italic style so it is visually
        distinct from real content.
        """
        strip = super().render_line(y)
        if not self.argument_hint:
            return strip

        # Only render on the last visual line of the document.
        _scroll_x, scroll_y = self.scroll_offset
        absolute_y = scroll_y + y

        last_doc_line = self.document.line_count - 1
        if absolute_y != last_doc_line:
            return strip

        line_text = self.document.get_line(absolute_y)
        content_cells = cell_len(line_text)

        if content_cells >= strip.cell_length:
            return strip

        prefix = strip.crop(0, content_cells)
        suffix = strip.crop(content_cells, strip.cell_length)
        suffix_width = suffix.cell_length

        # Optional: carry over cursor style to the first character of hint
        cursor_style = suffix._segments[0].style if suffix._segments else None
        
        hint_text = f" {self.argument_hint}"
        
        if cursor_style and self.has_focus:
            # If the cursor is at the end of the line, apply cursor style to the space
            first_char_style = _HINT_STYLE + cursor_style
            segments = [
                Segment(hint_text[0], first_char_style),
                Segment(hint_text[1:], _HINT_STYLE)
            ]
            hint_strip = Strip(segments, cell_length=cell_len(hint_text))
            
            # Since we consumed the cursor position, drop 1 from suffix
            if suffix_width > 0:
                suffix = suffix.crop(1, suffix_width)
        else:
            hint_segment = Segment(hint_text, _HINT_STYLE)
            hint_strip = Strip([hint_segment], cell_length=cell_len(hint_text))

        tail = Strip.join([hint_strip, suffix]).crop(0, suffix_width)
        return Strip.join([prefix, tail])

    def _find_chat_input(self) -> ChatInput | None:
        """Walk up the ancestor chain to find the ChatInput widget."""
        node = self.parent
        while node is not None:
            if isinstance(node, ChatInput):
                return node
            node = node.parent
        return None

    async def _on_key(self, event: events.Key) -> None:
        chat_input = self._find_chat_input()
        if chat_input is not None:
            handled = await chat_input._handle_key_event(event)
            if handled:
                return
        await super()._on_key(event)

    def on_paste(self, event: events.Paste) -> None:
        chat_input = self._find_chat_input()
        if chat_input is not None:
            chat_input.on_paste(event)


class ChatInput(Widget):
    """Multi-line chat input with prompt glyph (❯), mode detection, history,
    paste collapse, and inline slash command autocomplete.
    """

    DEFAULT_CSS = """
    ChatInput {
        height: auto;
    }

    ChatInput #input-box {
        height: auto;
        min-height: 3;
        max-height: 20;
        border: solid $primary;
        background: $background;
        color: $foreground;
        padding: 0;
    }

    ChatInput .input-row {
        height: auto;
        width: 100%;
        layout: horizontal;
        padding: 0 1;
    }

    ChatInput .input-prompt {
        width: 2;
        height: 1;
        color: $primary;
        text-style: bold;
    }

    ChatInput ChatTextArea {
        width: 1fr;
        height: auto;
        min-height: 1;
        max-height: 10;
        border: none;
        background: transparent;
        padding: 0;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss_or_clear", "Clear", show=False),
    ]

    mode: reactive[str] = reactive("normal")

    # ── Messages ────────────────────────────────────────

    class Submitted(Message):
        """Fired when the user submits prompt/command."""

        def __init__(self, value: str, mode: str = "normal") -> None:
            super().__init__()
            self.value = value
            self.mode = mode

    class ModeChanged(Message):
        """Fired when the input mode changes (for status bar updates)."""

        def __init__(self, mode: str) -> None:
            super().__init__()
            self.mode = mode

    class Typing(Message):
        """Fired on printable keystrokes."""

    class SlashCommandStarted(Message):
        """Fired when user begins typing a slash command."""

        def __init__(self, query: str) -> None:
            super().__init__()
            self.query = query

    class SlashCommandEnded(Message):
        """Fired when slash command context is exited."""

    class CancelRequested(Message):
        """Fired when user presses Ctrl+C on empty input."""

    # ── Constructor ─────────────────────────────────────

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._prompt_widget = Static("❯", id="input-prompt", classes="input-prompt")
        self._text_area = ChatTextArea(id="chat-text-area")
        self._autocomplete = AutocompletePopup()
        self._history: list[str] = []
        self._history_index: int = -1
        self._saved_draft: str = ""
        self._pasted_full_text: str | None = None
        # Maps command name (without leading /) to argument_hint string.
        self._argument_hints: dict[str, str] = {}
        self._rebuild_argument_hints()

    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal, Vertical
        with Vertical(id="input-box"):
            with Horizontal(classes="input-row"):
                yield self._prompt_widget
                yield self._text_area
            yield self._autocomplete

    # ── Properties & Delegation ─────────────────────────

    @property
    def text(self) -> str:
        return self._text_area.text

    @text.setter
    def text(self, value: str) -> None:
        self._text_area.text = value
        self._sync_mode()
        self._check_slash_command()

    def clear(self) -> None:
        self._text_area.clear()
        self._pasted_full_text = None
        self._autocomplete.hide_popup()
        self.mode = "normal"

    def focus(self, scroll_visible: bool = True) -> Self:
        self._text_area.focus(scroll_visible=scroll_visible)
        return self

    def focus_input(self) -> None:
        self.focus()

    # ── Mode Watcher ────────────────────────────────────

    def watch_mode(self, mode: str) -> None:
        """Update CSS classes and prompt glyph when mode changes."""
        self.remove_class("mode-command", "mode-shell", "mode-shell-incognito")
        glyph = MODE_DISPLAY_GLYPHS.get(mode, "❯")
        self._prompt_widget.update(glyph)
        if mode == "command":
            self.add_class("mode-command")
        elif mode == "shell":
            self.add_class("mode-shell")
        elif mode == "shell_incognito":
            self.add_class("mode-shell-incognito")
        self.post_message(self.ModeChanged(mode))

    # ── Event Handlers ──────────────────────────────────

    def on_paste(self, event: events.Paste | Any) -> None:
        """Handle paste events with collapsing for large multi-line payloads."""
        text = event.text
        lines = text.splitlines()
        if len(lines) > 5 or len(text) > 500:
            self._pasted_full_text = text
            preview = f"[Pasted {len(lines)} lines ({len(text)} chars) — press Enter to send]"
            self.text = preview
            event.prevent_default()
            event.stop()

    async def _handle_key_event(self, event: events.Key) -> bool:
        """Handle key presses — intercept submit/history, delegate rest to TextArea."""
        key = event.key

        # Check inline autocomplete popup interactions first
        popup = self._autocomplete
        if popup.is_visible:
            if key == "up":
                event.prevent_default()
                event.stop()
                popup.select_prev()
                return True
            if key == "down":
                event.prevent_default()
                event.stop()
                popup.select_next()
                return True
            if key in ("enter", "tab"):
                event.prevent_default()
                event.stop()
                popup.accept_selected(by_enter=(key == "enter"))
                return True

        # Submit on Enter (not shift+enter)
        if key == "enter":
            event.prevent_default()
            event.stop()
            self._submit_value()
            return True

        # History navigation
        if key in ("ctrl+up", "ctrl+p"):
            event.prevent_default()
            event.stop()
            self.action_history_prev()
            return True

        if key in ("ctrl+down", "ctrl+n"):
            event.prevent_default()
            event.stop()
            self.action_history_next()
            return True

        # Ctrl+C on empty input = cancel
        if key == "ctrl+c" and not self.text.strip():
            event.prevent_default()
            event.stop()
            self.post_message(self.CancelRequested())
            return True

        # After character is inserted in TextArea (handled synchronously after), sync mode
        self.call_after_refresh(self._after_key_sync)
        if event.is_printable or key == "backspace":
            self.post_message(self.Typing())

        return False

    def _after_key_sync(self) -> None:
        self._sync_mode()
        self._check_slash_command()
        self._update_argument_hint()

    # ── Mode Detection ──────────────────────────────────

    def _sync_mode(self) -> None:
        """Detect and update the input mode from current text content."""
        new_mode = detect_input_mode(self.text)
        if new_mode != self.mode:
            self.mode = new_mode

    def _check_slash_command(self) -> None:
        """Detect if input is slash command context and show/hide inline autocomplete."""
        current = self.text
        if self.mode == "command" or current.startswith("/"):
            query = current if current.startswith("/") else f"/{current}"
            query = query.split(maxsplit=1)[0]
            self._autocomplete.filter_query(query)
            self._autocomplete.show_popup()
            self.post_message(self.SlashCommandStarted(query))
        else:
            self._autocomplete.hide_popup()
            self.post_message(self.SlashCommandEnded())

    # ── Argument Hint Ghost Text ────────────────────────

    def _rebuild_argument_hints(self) -> None:
        """Rebuild the command-name -> argument-hint lookup from registry."""
        from dcoder.ui.command_registry import get_all_entries

        self._argument_hints = {
            entry.name.removeprefix("/"): entry.argument_hint
            for entry in get_all_entries()
            if entry.argument_hint
        }

    def _update_argument_hint(self) -> None:
        """Show or clear inline ghost text for slash-command argument hints.

        Sets ``ChatTextArea.argument_hint`` when the input is a known slash
        command followed by a trailing space with no args typed yet.
        For example, typing ``/rubric `` shows dim ``[set|next|show|clear|…]``.
        """
        if self.mode == "command":
            text = self._text_area.text
            # Command + single trailing space, no args yet
            if text.endswith(" ") and text.count(" ") == 1:
                command = text.rstrip().lstrip("/")
                hint = self._argument_hints.get(command, "")
                if hint:
                    self._text_area.argument_hint = hint
                    return

        self._text_area.argument_hint = ""

    # ── Submit ──────────────────────────────────────────

    def _submit_value(self) -> None:
        """Submit the current text with detected mode."""
        content = self._pasted_full_text if self._pasted_full_text else self.text.strip()
        self._pasted_full_text = None

        if not content:
            return

        mode = detect_input_mode(content)

        if not self._history or self._history[-1] != content:
            self._history.append(content)
        self._history_index = -1
        self._saved_draft = ""

        self.clear()
        self.mode = "normal"

        self.post_message(self.SlashCommandEnded())
        self.post_message(self.Submitted(content, mode))

    # ── History ─────────────────────────────────────────

    def action_history_prev(self) -> None:
        """Navigate backward in history."""
        if not self._history:
            return
        if self._history_index == -1:
            self._saved_draft = self.text
            self._history_index = len(self._history) - 1
        elif self._history_index > 0:
            self._history_index -= 1

        self.text = self._history[self._history_index]

    def action_history_next(self) -> None:
        """Navigate forward in history."""
        if self._history_index == -1:
            return
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self.text = self._history[self._history_index]
        else:
            self._history_index = -1
            self.text = self._saved_draft

    def action_dismiss_or_clear(self) -> None:
        """Clear input text and end slash command mode."""
        self.clear()
