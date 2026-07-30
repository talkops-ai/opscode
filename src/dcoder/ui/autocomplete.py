"""Autocomplete popup widget for slash commands.

Displays floating overlay matching user input against registered commands
and skill-derived commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static

from dcoder.ui.command_registry import CommandEntry, get_all_entries

if TYPE_CHECKING:
    from dcoder.ui.command_registry import SlashCommand


class AutocompleteRow(Static):
    """Single command entry row in autocomplete popup."""

    DEFAULT_CSS = """
    AutocompleteRow {
        padding: 0 1;
        height: 1;
    }
    AutocompleteRow:hover {
        background: $panel;
    }
    AutocompleteRow.--selected {
        background: $primary;
        color: $background;
        text-style: bold;
    }
    """

    def __init__(self, entry: CommandEntry, is_selected: bool = False) -> None:
        self.entry = entry
        self._is_selected = is_selected
        super().__init__(self._build_text(entry), markup=False)
        if is_selected:
            self.add_class("--selected")

    def _build_text(self, entry: CommandEntry) -> Text:
        render_text = Text()
        render_text.append(entry.name, style="bold")
        if entry.argument_hint:
            render_text.append(f" {entry.argument_hint}", style="italic")
        render_text.append(f" — {entry.description}")
        return render_text

    def update_entry(self, entry: CommandEntry, is_selected: bool) -> None:
        self.entry = entry
        self.update(self._build_text(entry))
        self.set_selected(is_selected)

    def set_selected(self, selected: bool) -> None:
        self._is_selected = selected
        if selected:
            self.add_class("--selected")
        else:
            self.remove_class("--selected")


class AutocompletePopup(VerticalScroll):
    """Inline autocomplete popup for slash commands — rendered inside the input box."""

    DEFAULT_CSS = """
    AutocompletePopup {
        height: auto;
        max-height: 10;
        width: 100%;
        background: $surface;
        border-top: solid $primary;
        scrollbar-size-vertical: 1;
        scrollbar-gutter: stable;
        display: none;
    }
    """

    class CommandSelected(Message):
        """Fired when user accepts a command selection."""

        def __init__(self, command_name: str, by_enter: bool = False) -> None:
            super().__init__()
            self.command_name = command_name
            self.by_enter = by_enter

    class Dismissed(Message):
        """Fired when autocomplete popup is dismissed."""

    def __init__(self, extra_commands: list[SlashCommand] | None = None) -> None:
        super().__init__(id="autocomplete-popup")
        self._all_entries = get_all_entries(extra_commands)
        self._filtered_entries: list[CommandEntry] = list(self._all_entries)
        self._selected_index = 0
        self._rows: list[AutocompleteRow] = []

    def show_popup(self) -> None:
        """Make the popup visible and ensure rows are built."""
        self.styles.display = "block"
        self._rebuild_rows()

    def hide_popup(self) -> None:
        """Hide the popup without removing it from the DOM."""
        self.styles.display = "none"

    @property
    def is_visible(self) -> bool:
        """Whether the popup is currently displayed."""
        return self.styles.display != "none"

    def on_mount(self) -> None:
        self._rebuild_rows()

    def filter_query(self, query: str) -> None:
        """Filter command list by query string."""
        q = query.lower().strip()
        if not q or q == "/":
            self._filtered_entries = list(self._all_entries)
        else:
            self._filtered_entries = [
                entry
                for entry in self._all_entries
                if q in entry.name.lower()
                or q in entry.description.lower()
                or q in entry.hidden_keywords.lower()
            ]

        self._selected_index = 0
        if self.is_visible:
            self._rebuild_rows()

    def select_next(self) -> None:
        """Move selection down and scroll into view."""
        if not self._rows:
            return
        self._rows[self._selected_index].set_selected(False)
        self._selected_index = (self._selected_index + 1) % len(self._rows)
        self._rows[self._selected_index].set_selected(True)
        self._scroll_selected_into_view()

    def select_prev(self) -> None:
        """Move selection up and scroll into view."""
        if not self._rows:
            return
        self._rows[self._selected_index].set_selected(False)
        self._selected_index = (self._selected_index - 1) % len(self._rows)
        self._rows[self._selected_index].set_selected(True)
        self._scroll_selected_into_view()

    def _scroll_selected_into_view(self) -> None:
        """Scroll the selected row into view."""
        if not self._rows or self._selected_index >= len(self._rows):
            return
        if self._selected_index == 0:
            self.scroll_home(animate=False)
        else:
            self._rows[self._selected_index].scroll_visible(animate=False)

    def accept_selected(self, by_enter: bool = False) -> str | None:
        """Accept currently selected command."""
        if self._filtered_entries and 0 <= self._selected_index < len(self._filtered_entries):
            entry = self._filtered_entries[self._selected_index]
            self.post_message(self.CommandSelected(entry.name, by_enter=by_enter))
            return entry.name
        return None

    def _rebuild_rows(self) -> None:
        """Re-render row widgets efficiently in place."""
        if not self.is_mounted:
            return

        existing = len(self._rows)
        needed = len(self._filtered_entries)

        # Update existing rows in place
        for idx in range(min(existing, needed)):
            entry = self._filtered_entries[idx]
            is_selected = (idx == self._selected_index)
            self._rows[idx].update_entry(entry, is_selected)

        # Remove excess rows
        if existing > needed:
            for row in self._rows[needed:]:
                row.remove()
            del self._rows[needed:]

        # Mount new rows if needed
        if needed > existing:
            new_rows: list[AutocompleteRow] = []
            for idx in range(existing, needed):
                entry = self._filtered_entries[idx]
                is_selected = (idx == self._selected_index)
                row = AutocompleteRow(entry, is_selected=is_selected)
                new_rows.append(row)
                self._rows.append(row)
            self.mount(*new_rows)

        self._scroll_selected_into_view()
