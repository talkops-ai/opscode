"""Sub-agent panel widget for the DCoder TUI.

Provides parallel column layout for multi-subagent execution and live token streaming.
"""

from __future__ import annotations

from typing import Any

from rich.markdown import Markdown as RichMarkdown
from rich.text import Text
from textual.containers import HorizontalScroll, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Static


class SubagentColumn(Vertical):
    """Single subagent execution column."""

    DEFAULT_CSS = """
    SubagentColumn {
        width: 38;
        height: auto;
        max-height: 12;
        padding: 0 1;
        margin-right: 1;
        background: $background;
        border: solid $primary;
    }
    SubagentColumn.completed {
        border: solid $success;
        height: auto;
    }
    SubagentColumn .title {
        color: $primary;
        text-style: bold;
    }
    """

    def __init__(self, agent_name: str, task: str) -> None:
        super().__init__()
        self.agent_name = agent_name
        self.task_desc = task
        self._tokens: list[str] = []
        self._content = Static("", id=f"content-{agent_name}")

    def compose(self):
        title = Text(f"🤖 {self.agent_name}\n", style="bold cyan")
        title.append(f"Task: {self.task_desc[:40]}...", style="dim")
        yield Static(title, classes="title")
        with VerticalScroll(id=f"body-{self.agent_name}"):
            yield self._content

    def append_token(self, token: str) -> None:
        """Append token and update single content widget."""
        self._tokens.append(token)
        full_text = "".join(self._tokens)
        self._content.update(RichMarkdown(full_text))

    def finish(self) -> None:
        """Mark column as completed and collapse to summary."""
        self.add_class("completed")
        title = Text(f"✓ {self.agent_name} (completed)\n", style="bold green")
        title.append(f"Task: {self.task_desc[:40]}...", style="dim")
        self.query_one(".title", Static).update(title)


class SubagentPanel(HorizontalScroll):
    """Multi-column container for parallel subagent streaming."""

    DEFAULT_CSS = """
    SubagentPanel {
        height: auto;
        max-height: 14;
        margin: 1 0 0 2;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._columns: dict[str, SubagentColumn] = {}

    def spawn_subagent(self, agent_name: str, task: str) -> None:
        """Spawn a new subagent column."""
        if agent_name not in self._columns:
            col = SubagentColumn(agent_name, task)
            self._columns[agent_name] = col
            self.mount(col)

    def append_token(self, agent_name: str, token: str) -> None:
        """Stream token into target subagent column."""
        if agent_name in self._columns:
            self._columns[agent_name].append_token(token)

    def finish_subagent(self, agent_name: str) -> None:
        """Mark subagent column as complete."""
        if agent_name in self._columns:
            self._columns[agent_name].finish()

