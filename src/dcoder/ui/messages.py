"""Message display widgets for the DCoder TUI.

Provides ``MessageList``, ``UserMessage``, ``AssistantMessage``,
``ToolCallMessage``, ``SkillMessage``, ``DiffMessage``, ``QueuedUserMessage``,
``ToolGroupSummary``, and ``SystemMessage`` widgets.
Matches Claude Code and reference dcode visual styling.
"""

from __future__ import annotations

import time
import logging
from typing import Any, ClassVar

from rich.markdown import Markdown as RichMarkdown
from rich.text import Text
from rich.console import Console as RichConsole, ConsoleOptions, RenderResult
from rich.styled import Styled
from rich.theme import Theme
from textual import events
from textual.containers import VerticalScroll
from textual.widgets import Static
from textual.content import Content, Span
from textual.style import Style

from dcoder.ui.diff import compose_diff_lines
from dcoder.ui.tool_display import (
    format_tool_display,
    format_tool_result_summary,
)

logger = logging.getLogger(__name__)


# ── Individual Message Widgets ───────────────────────────


class UserMessage(Static):
    """A user message rendered with prompt prefix and border-left styling."""

    DEFAULT_CSS = """
    UserMessage {
        height: auto;
        padding: 0 1;
        margin: 1 0 0 0;
        background: $panel;
        border-left: wide $primary;
        pointer: text;
    }
    """

    def __init__(self, content: str) -> None:
        self._raw_content = content
        self._timestamp = time.strftime("%H:%M:%S")
        self._show_timestamp = False
        # Pass empty string — render() provides the live content on every repaint.
        super().__init__("")

    def set_timestamp_visible(self, visible: bool) -> None:
        self._show_timestamp = visible
        self.refresh()

    def _prefix_and_body(self) -> tuple[tuple[str, str], str]:
        """Compute the styled prefix and body with its trigger stripped."""
        from dcoder.ui.theme import get_theme_colors
        from dcoder.ui.chat_input import detect_input_mode, MODE_PREFIXES, MODE_DISPLAY_GLYPHS

        content = self._raw_content
        mode = detect_input_mode(content)
        colors = get_theme_colors(self)

        if mode != "normal":
            prefix_text = MODE_PREFIXES.get(mode, "")
            glyph = MODE_DISPLAY_GLYPHS.get(mode, prefix_text)

            return (
                (f"{glyph} ", f"bold {colors.primary}"),
                content[len(prefix_text):]
            )

        return ("> ", f"bold {colors.primary}"), content

    def render(self) -> Content:
        """Render the styled user message with live theme colors.

        Textual calls this on every repaint, so the glyph color and border
        always reflect the currently active theme — even after a ``/theme``
        switch.

        Returns:
            Styled ``Content`` with mode prefix and message body.
        """
        prefix, body = self._prefix_and_body()
        parts: list[str | tuple[str, str]] = [prefix, body]
        if self._show_timestamp:
            parts.append((f"  [{self._timestamp}]", "dim italic"))
        return Content.assemble(*parts)


class QueuedUserMessage(Static):
    """A user message currently waiting in the processing queue."""

    DEFAULT_CSS = """
    QueuedUserMessage {
        height: auto;
        padding: 0 1;
        margin: 1 0 0 0;
        background: $panel;
        opacity: 0.7;
        color: $foreground;
    }
    """

    def __init__(self, content: str) -> None:
        self._raw_content = content
        super().__init__("")

    def render(self) -> Content:
        """Render the queued message with live theme colors."""
        return Content.assemble(
            ("⏳ Queued: ", "italic bold $warning"),
            (self._raw_content, "italic dim"),
        )


class AssistantMessage(Static):
    """A streaming message from the AI assistant with bullet dot prefix and markdown rendering."""

    DEFAULT_CSS = """
    AssistantMessage {
        height: auto;
        padding: 0 1;
        margin: 1 0 0 0;
        color: $foreground;
        pointer: text;
    }
    """

    def __init__(self, content: str = "") -> None:
        super().__init__("")
        self._fragments: list[str] = []
        self._last_update_time: float = 0.0
        self._is_streaming: bool = True
        self._markdown_cache: tuple[int, Content] | None = None
        if content:
            self._fragments.append(content)
            self._is_streaming = False

    @property
    def content_text(self) -> str:
        """Raw text content accumulated so far."""
        return "".join(self._fragments)

    @property
    def is_streaming(self) -> bool:
        """Whether the message is actively streaming tokens."""
        return self._is_streaming

    def _format_assistant_content(self, text: str) -> str:
        """Add bullet prefix '● ' to non-empty response blocks if not already present."""
        if not text or text.strip().startswith(("●", "•", ">", "#", "```")):
            return text
        return f"● {text}"

    def append_token(self, token: str) -> None:
        """Append a streaming text token and update render with 50ms throttling."""
        self._is_streaming = True
        self._fragments.append(token)
        now = time.time()
        if now - self._last_update_time >= 0.05 or len(self._fragments) == 1:
            self._last_update_time = now
            self._markdown_cache = None
            self.refresh()

    def finish(self) -> None:
        """Mark the message as complete (final markdown render)."""
        self._is_streaming = False
        if not self._fragments:
            self.remove()
        else:
            self._markdown_cache = None
            self.refresh()

    def render(self) -> Content:
        width = self.content_size.width
        if width <= 0:
            width = 80
        full_text = "".join(self._fragments)
        formatted = self._format_assistant_content(full_text)
        if self._markdown_cache is None or self._markdown_cache[0] != width:
            try:
                console = self.app.console
            except Exception:
                console = None
            content = _markdown_to_content(formatted, width, console)
            self._markdown_cache = (width, content)
        return self._markdown_cache[1]


class ToolCallMessage(Static):
    """A tool-call notification with Claude Code style tree output, dot prefix, and toggleable detail."""

    DEFAULT_CSS = """
    ToolCallMessage {
        height: auto;
        padding: 0 1;
        margin: 0 0 0 0;
        color: $foreground;
    }
    ToolCallMessage:hover {
        background: $surface;
    }
    """

    def __init__(self, name: str, call_id: str, args: dict[str, Any]) -> None:
        self._tool_name = name if (name and name != "None") else "tool"
        self._call_id = call_id
        self._args = args or {}
        self._result: str | None = None
        self._status = "running"
        self._expanded = False

        header_str = format_tool_display(self._tool_name, self._args, prefix="●")
        display = Text(header_str, style="bold cyan")

        super().__init__(display)

    @property
    def tool_name(self) -> str:
        return self._tool_name

    def set_result(self, result: str, success: bool = True, name: str | None = None) -> None:
        """Update with tool result and final status using tree branch summary."""
        if name and name != "None":
            self._tool_name = name
        elif not self._tool_name or self._tool_name == "None":
            self._tool_name = "tool"

        self._result = result
        self._status = "success" if success else "error"

        icon = "●"
        style = "bold green" if success else "bold red"
        header_str = format_tool_display(self._tool_name, self._args, prefix=icon)
        display = Text(header_str, style=style)

        summary_str = format_tool_result_summary(self._tool_name, result)
        display.append(f"\n  {summary_str}", style="dim")
        self.update(display)

    def on_click(self) -> None:
        """Toggle between compact tree summary and full detailed result on click."""
        if not self._result:
            return
        self._expanded = not self._expanded
        icon = "●"
        style = "bold green" if self._status == "success" else "bold red"
        header_str = format_tool_display(self._tool_name, self._args, prefix=icon)
        display = Text(header_str, style=style)

        if self._expanded:
            display.append(f"\n{self._result}", style="dim")
        else:
            summary_str = format_tool_result_summary(self._tool_name, self._result)
            display.append(f"\n  {summary_str}", style="dim")
        self.update(display)


class SkillMessage(Static):
    """Card displaying loaded skill knowledge packs with source indicators."""

    DEFAULT_CSS = """
    SkillMessage {
        padding: 0 1;
        margin: 0 0 0 0;
        color: $foreground;
    }
    SkillMessage:hover {
        background: $surface;
    }
    """

    def __init__(self, name: str, content: str, source: str = "workspace") -> None:
        self._skill_name = name
        self._content = content
        self._source = source
        self._expanded = False

        display = Text(f"● Skill Loaded: {name} ", style="bold green")
        display.append(f"(source: {source})", style="dim italic")
        display.append(f"\n  ⎿ {content[:100]}...", style="dim")
        super().__init__(display)

    def on_click(self) -> None:
        """Toggle between truncated summary and full content view."""
        self._expanded = not self._expanded
        display = Text(f"● Skill Loaded: {self._skill_name} ", style="bold green")
        display.append(f"(source: {self._source})", style="dim italic")
        if self._expanded:
            display.append(f"\n{self._content}", style="dim")
        else:
            display.append(f"\n  ⎿ {self._content[:100]}...", style="dim")
        self.update(display)


class DiffMessage(Static):
    """Inline diff display widget."""

    DEFAULT_CSS = """
    DiffMessage {
        padding: 0 1;
        margin: 1 0 0 0;
        background: $background;
        border: solid $panel;
        pointer: text;
    }
    """

    def __init__(self, patch_or_diff: str, file_path: str = "") -> None:
        diff_lines = compose_diff_lines(patch_or_diff)
        header = Text(f"📝 Diff: {file_path}\n" if file_path else "📝 Diff\n", style="bold cyan")
        super().__init__(header + diff_lines)


class ToolGroupSummary(Static):
    """Compact summary card for multiple tool executions."""

    DEFAULT_CSS = """
    ToolGroupSummary {
        padding: 0 1;
        margin: 0 0 0 0;
        color: $foreground;
    }
    """

    def __init__(self, total: int, succeeded: int, failed: int) -> None:
        display = Text(f"● Executed {total} tools ", style="bold green")
        display.append(f"({succeeded} ✓", style="green")
        if failed > 0:
            display.append(f", {failed} ✗", style="red")
        display.append(")", style="bold")
        super().__init__(display)


class ErrorMessage(Static):
    """An error message widget matching dcode styling."""

    DEFAULT_CSS = """
    ErrorMessage {
        height: auto;
        padding: 1 2;
        margin: 1 0 0 0;
        background: $surface;
        color: $error;
        pointer: text;
    }
    """

    def __init__(self, content: str, **kwargs: Any) -> None:
        self._raw_content = content
        text = Text()
        text.append("● Error: ", style="bold red")
        text.append(content, style="red")
        super().__init__(text, **kwargs)


class ThinkingMessage(Static):
    """Collapsible widget displaying internal model reasoning / thinking content matching Claude Code style."""

    DEFAULT_CSS = """
    ThinkingMessage {
        height: auto;
        padding: 0 1;
        margin: 0 0 1 0;
        color: $text-muted;
    }
    ThinkingMessage:hover {
        background: $surface;
    }
    """

    def __init__(self, content: str = "", duration_seconds: float = 0.0) -> None:
        self._content = content
        self._duration_seconds = duration_seconds
        self._expanded = False
        super().__init__(self._build_display())

    def update_thinking(self, content: str, duration_seconds: float | None = None) -> None:
        """Update content and duration dynamically during stream."""
        self._content = content
        if duration_seconds is not None:
            self._duration_seconds = duration_seconds
        self.update(self._build_display())

    def _build_display(self) -> Text:
        arrow = "˅" if self._expanded else "❯"
        dur_str = f" for {int(self._duration_seconds)}s" if self._duration_seconds > 0 else ""
        display = Text(f"Thought{dur_str} {arrow}", style="dim bold")

        if self._expanded and self._content:
            display.append(f"\n\n{self._content.strip()}", style="dim")
        return display

    def on_click(self, event: events.Click) -> None:
        """Toggle expand/collapse on click."""
        event.stop()
        self._expanded = not self._expanded
        self.update(self._build_display())


class SystemMessage(Static):
    """A system/command-response info message.

    Styled muted+italic to visually distinguish command output from the
    purple ``UserMessage`` glyph/border in command mode.  Markdown content
    (e.g. ``/rubric`` usage with code blocks) is rendered lazily via
    ``_markdown_to_content`` so it reflows on width changes.  Plain one-liner
    messages receive a ``● `` bullet prefix; multi-line or markdown messages
    are passed through as-is.
    """


    DEFAULT_CSS = """
    SystemMessage {
        padding: 0 1;
        margin: 1 0 0 0;
        height: auto;
        color: $primary;
        pointer: text;
    }
    """

    def __init__(self, content: str) -> None:
        self._raw_content = content
        self._timestamp = time.strftime("%H:%M:%S")
        self._show_timestamp = False
        self._markdown_cache: tuple[int, Content] | None = None
        super().__init__("")
        # Disable auto_links: the Reactive setter avoids the flicker loop caused
        # by Style.__add__ generating a fresh random _link_id on every render.
        self.auto_links = False

    def set_timestamp_visible(self, visible: bool) -> None:
        self._show_timestamp = visible
        self._markdown_cache = None
        self.refresh()

    def _build_display_text(self) -> str:
        """Return display text, adding bullet prefix for single-line plain messages.

        Multi-line content or content that already has markdown structure
        (``**``, `` ``` ``, ``/``) is left untouched so rendered markdown
        headings and code blocks are not contaminated by a leading bullet.
        """
        content = self._raw_content
        if self._show_timestamp:
            content = f"{content}  *[{self._timestamp}]*"
        # Only prepend ● for short single-line messages that are not already
        # markdown-formatted (code blocks, bold, or slash-command references).
        is_multiline = "\n" in content
        is_markdown = any(tok in content for tok in ("```", "**", "__", "# ", "- ", "  /"))
        already_bulleted = content.startswith("● ") or content.startswith("🧹")
        if not already_bulleted and not is_multiline and not is_markdown:
            content = f"● {content}"
        return content

    def render(self) -> Content:
        """Render message content, laying out markdown to the current widget width.

        Results are cached by width — late-bound style tokens (``dim``, ``bold``,
        ANSI colors) are resolved against the active theme at display time, so
        cached ``Content`` re-colors correctly on a ``/theme`` switch.

        Returns:
            Styled ``Content`` for display.
        """
        width = self.content_size.width
        if width <= 0:
            width = self.container_size.width
            if width <= 0:
                try:
                    width = self.app.size.width
                except Exception:
                    width = 80
        text = self._build_display_text()
        if self._markdown_cache is None or self._markdown_cache[0] != width:
            try:
                console = self.app.console
            except Exception:
                console = None
            content = _markdown_to_content(text, width, console)
            self._markdown_cache = (width, content)
        return self._markdown_cache[1]


# ── Message List Container ───────────────────────────────


class MessageList(VerticalScroll):
    """Scrollable list of conversation messages with auto-scroll lock controls."""

    DEFAULT_CSS = """
    MessageList {
        height: 1fr;
        layout: stream;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._current_assistant: AssistantMessage | None = None
        self._tool_calls: dict[str, ToolCallMessage] = {}
        self._auto_scroll_locked = True

    def on_scroll_up(self) -> None:
        """Suspend auto-scroll when user manually scrolls up."""
        self._auto_scroll_locked = False

    def add_thinking_message(self, content: str = "", duration_seconds: float = 0.0) -> ThinkingMessage:
        """Add a thinking message widget to the conversation."""
        msg = ThinkingMessage(content=content, duration_seconds=duration_seconds)
        self.mount(msg)
        if self._auto_scroll_locked:
            self._scroll_to_end()
        return msg

    def add_user_message(self, text: str) -> None:
        """Add a user message and reset auto-scroll."""
        self._auto_scroll_locked = True
        self.mount(UserMessage(text))
        self._scroll_to_end()

    def add_queued_user_message(self, text: str) -> QueuedUserMessage:
        """Add a queued user message."""
        msg = QueuedUserMessage(text)
        self.mount(msg)
        self._scroll_to_end()
        return msg

    def remove_queued_user_messages(self) -> None:
        """Remove any QueuedUserMessage widgets currently in the list."""
        for msg in self.query(QueuedUserMessage):
            msg.remove()

    def start_assistant_message(self) -> None:
        """Start a streaming assistant message."""
        msg = AssistantMessage()
        self._current_assistant = msg
        self.mount(msg)
        self._scroll_to_end()

    def append_assistant_token(self, token: str) -> None:
        """Append a token to current assistant message."""
        if self._current_assistant is None:
            self.start_assistant_message()
        if self._current_assistant is not None:
            self._current_assistant.append_token(token)
            if self._auto_scroll_locked:
                self._scroll_to_end()

    def finish_assistant_message(self) -> None:
        """Finalize assistant message."""
        if self._current_assistant:
            self._current_assistant.finish()
            self._current_assistant = None
            self._scroll_to_end()

    def add_tool_call(
        self, name: str, call_id: str, args: dict[str, Any]
    ) -> None:
        """Add a tool-call widget."""
        msg = ToolCallMessage(name, call_id, args)
        self._tool_calls[call_id] = msg
        self.mount(msg)
        self._scroll_to_end()

    def update_tool_result(
        self, call_id: str, result: str, success: bool = True, name: str | None = None
    ) -> None:
        """Update a tool-call widget with its result."""
        if call_id and call_id in self._tool_calls:
            self._tool_calls[call_id].set_result(result, success=success, name=name)
        else:
            msg_name = name if (name and name != "None") else "tool"
            msg = ToolCallMessage(msg_name, call_id or "tool_call", {})
            msg.set_result(result, success=success, name=msg_name)
            if call_id:
                self._tool_calls[call_id] = msg
            self.mount(msg)
        self._scroll_to_end()

    def add_skill_message(self, name: str, content: str) -> None:
        """Add a skill loaded card."""
        self.mount(SkillMessage(name, content))
        self._scroll_to_end()

    def add_diff_message(self, patch: str, file_path: str = "") -> None:
        """Add an inline diff message."""
        self.mount(DiffMessage(patch, file_path))
        self._scroll_to_end()

    def add_tool_group_summary(self, total: int, succeeded: int, failed: int) -> None:
        """Add a tool group summary card."""
        self.mount(ToolGroupSummary(total, succeeded, failed))
        self._scroll_to_end()

    def add_error_message(self, text: str) -> None:
        """Add an error message."""
        self.mount(ErrorMessage(text))
        self._scroll_to_end()

    def add_system_message(self, text: str) -> None:
        """Add a system/info message."""
        self.mount(SystemMessage(text))
        self._scroll_to_end()

    def clear(self) -> None:
        """Clear all child widgets."""
        self.remove_children()
        self._current_assistant = None
        self._tool_calls.clear()

    def set_timestamps_visible(self, visible: bool) -> None:
        """Show or hide timestamp footers across all mounted messages."""
        self._timestamps_visible = visible
        for child in self.children:
            fn = getattr(child, "set_timestamp_visible", None)
            if callable(fn):
                fn(visible)

    def _scroll_to_end(self) -> None:
        """Scroll to the end if auto-scroll is locked."""
        if self._auto_scroll_locked:
            self.scroll_end(animate=False)


class _MutedRichMarkdown:
    _THEME_OVERRIDES: ClassVar[dict[str, str]] = {
        "markdown.h1": "bold underline",
        "markdown.h2": "bold underline",
        "markdown.h3": "bold",
        "markdown.h4": "italic",
        "markdown.table.header": "bold",
        "markdown.table.border": "",
    }

    def __init__(self, markup: str) -> None:
        self._markdown = RichMarkdown(markup)
        self._markup = markup

    def __rich_console__(
        self, console: RichConsole, options: ConsoleOptions
    ) -> RenderResult:
        theme = Theme(self._THEME_OVERRIDES, inherit=True)
        try:
            with console.use_theme(theme):
                yield from Styled(self._markdown, "dim").__rich_console__(
                    console, options
                )
        except Exception:
            logger.warning(
                "Rich markdown rendering failed; falling back to plain text",
                exc_info=True,
            )
            yield from Styled(self._markup, "dim italic").__rich_console__(
                console, options
            )


_markdown_style_conversion_warned = [False]


def _markdown_to_content(
    markup: str, width: int, console: RichConsole | None = None
) -> Content:
    from rich.console import Console
    from rich.segment import Segment

    render_width = max(width, 1)
    if console is None:
        console = Console(width=render_width)
    segments = console.render(
        _MutedRichMarkdown(markup), console.options.update_width(render_width)
    )
    content_lines: list[Content] = []
    for line in Segment.split_lines(segments):
        text = "".join(segment.text for segment in line)
        stripped = text.rstrip()
        spans: list[Span] = []
        position = 0
        for segment in line:
            start = position
            position += len(segment.text)
            if start >= len(stripped):
                break
            end = min(position, len(stripped))
            if segment.style is not None and end > start:
                try:
                    style = Style.from_rich_style(segment.style)
                except Exception:
                    if not _markdown_style_conversion_warned[0]:
                        _markdown_style_conversion_warned[0] = True
                        logger.warning(
                            "Failed to convert a markdown style; markdown will "
                            "render without some styling (later occurrences log "
                            "at debug)",
                            exc_info=True,
                        )
                    else:
                        logger.debug(
                            "Skipping unconvertible markdown style", exc_info=True
                        )
                else:
                    spans.append(Span(start, end, style))
        content_lines.append(Content(stripped, spans))
    while content_lines and not content_lines[-1].plain:
        content_lines.pop()
    return Content("\n").join(content_lines)
