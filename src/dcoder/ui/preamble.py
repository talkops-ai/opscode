"""Message widgets."""

from __future__ import annotations

import ast
import json
import logging
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from textual import on
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.css.query import NoMatches
from textual.events import Click
from textual.geometry import Offset
from textual.message import Message
from textual.message_pump import NoActiveAppError
from textual.reactive import var
from textual.selection import Selection
from textual.style import Style as TStyle
from textual.widgets import Static

from deepagents_code import theme
from deepagents_code._ask_user_types import (
    ASK_USER_ANSWERED_SUMMARY,
    ASK_USER_FAILED_SUMMARY,
    AskUserRowSummary,
)
from deepagents_code.config import (
    MODE_DISPLAY_GLYPHS,
    detect_mode_prefix,
    get_glyphs,
    is_ascii_mode,
)
from deepagents_code.file_ops import is_sensitive_file_path
from deepagents_code.formatting import format_duration
from deepagents_code.input import EMAIL_PREFIX_PATTERN, INPUT_HIGHLIGHT_PATTERN
from deepagents_code.tool_display import (
    EXECUTE_HEADER_MAX_LENGTH,
    JS_EVAL_HEADER_MAX_LENGTH,
    format_tool_display,
)
from deepagents_code.tui.widgets._js_eval_display import (
    JsEvalBlock,
    JsEvalError,
    JsEvalResult,
    JsEvalStdout,
    parse_js_eval_blocks,
)
from deepagents_code.tui.widgets._links import (
    event_targets_link,
    open_checked_url_async,
    open_style_link,
)
from deepagents_code.tui.widgets.diff import compose_diff_lines
from deepagents_code.unicode_security import render_with_unicode_markers

if TYPE_CHECKING:
    from collections.abc import Iterable

    from rich.console import (
        Console as RichConsole,
        ConsoleOptions,
        RenderResult,
    )
    from textual.app import ComposeResult
    from textual.events import MouseMove
    from textual.timer import Timer
    from textual.widget import Widget
    from textual.widgets import Markdown
    from textual.widgets._markdown import MarkdownStream

    from deepagents_code.input import MediaTracker
    from deepagents_code.theme import ThemeColors

logger = logging.getLogger(__name__)


def _mode_color(mode: str | None, widget_or_app: object | None = None) -> str:
    """Return the hex color string for a mode, falling back to primary.

    Args:
        mode: Mode name (e.g. `'shell'`, `'command'`) or `None`.
        widget_or_app: Textual widget or `App` for theme-aware lookup.

    Returns:
        Color string from the active theme's `ThemeColors`.
    """
    colors = theme.get_theme_colors(widget_or_app)
    if not mode:
        return colors.primary
    if mode == "shell_incognito":
        return colors.mode_incognito
    if mode == "shell":
        return colors.mode_bash
    if mode == "command":
        return colors.mode_command
    logger.warning("Missing color for mode '%s'; falling back to primary.", mode)
    return colors.primary


@dataclass(frozen=True, slots=True)
