"""Welcome banner & first-run onboarding widget for DCoder TUI.

Displays a Claude-Code-inspired two-panel split layout:
  Left  — TalkOps pixel logo, version, project directory, connection status.
  Right — Prompt help, discovered skills list, loaded subagents list.

Lists that exceed MAX_DISPLAY_ITEMS show a clickable "…more" span that
opens a WelcomeDetailPopup modal with the full list and descriptions.

The left panel status indicator transitions from yellow "starting" to
green "connected" when the agent server becomes ready.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from rich.console import ConsoleRenderable, Group
from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

logger = logging.getLogger(__name__)

# Maximum number of items shown inline before truncating with "…more".
MAX_DISPLAY_ITEMS = 5

# Maximum character width for the inline list before truncating.
# Applied after MAX_DISPLAY_ITEMS to catch long names that wrap.
MAX_INLINE_CHARS = 55


# ── TalkOps pixel logo ────────────────────────────────────────────
# Renders the TalkOps favicon (speech-bubble + infinity crossover)
# using rich-pixels half-block characters for true-color pixel art.
# Generated programmatically via PIL — no external file dependency.

_LOGO_CACHE: ConsoleRenderable | None = None  # Cache the Pixels renderable


def _build_logo_pixels() -> ConsoleRenderable:
    """Return a rich-pixels `Pixels` renderable of the TalkOps favicon."""
    global _LOGO_CACHE  # noqa: PLW0603
    if _LOGO_CACHE is not None:
        return _LOGO_CACHE

    try:
        from PIL import Image, ImageDraw
        from rich_pixels import Pixels
    except ImportError:
        logger.debug("rich-pixels / Pillow not available; falling back to text logo")
        return _build_logo_text_fallback()

    blue = (31, 122, 203, 255)   # #1F7ACB
    green = (122, 193, 67, 255)  # #7AC143

    size = 16  # ~8 terminal rows × 16 cols
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 48.0  # scale factor from 48px reference design

    # Speech-bubble outline
    draw.ellipse(
        [int(4 * s), int(2 * s), int(44 * s), int(34 * s)],
        outline=blue,
        width=max(1, int(2 * s)),
    )
    # Left tail (blue — user side)
    draw.polygon(
        [(int(10 * s), int(31 * s)), (int(4 * s), int(44 * s)), (int(18 * s), int(33 * s))],
        fill=blue,
    )
    # Right tail (blue — agent side)
    draw.polygon(
        [(int(30 * s), int(31 * s)), (int(44 * s), int(44 * s)), (int(38 * s), int(33 * s))],
        fill=blue,
    )
    # Left infinity loop (blue)
    draw.ellipse(
        [int(12 * s), int(11 * s), int(26 * s), int(27 * s)],
        outline=blue,
        width=max(1, int(2 * s)),
    )
    # Right infinity loop (green)
    draw.ellipse(
        [int(22 * s), int(11 * s), int(36 * s), int(27 * s)],
        outline=green,
        width=max(1, int(2 * s)),
    )

    _LOGO_CACHE = Pixels.from_image(img)
    return _LOGO_CACHE


def _build_logo_text_fallback() -> Text:
    """Fallback plain-text logo if rich-pixels is unavailable."""
    t = Text()
    blue = "#1F7ACB"
    green = "#7AC143"
    t.append("  ╭────────────╮\n", style=blue)
    t.append("  │  ", style=blue)
    t.append("∞", style=f"bold {blue}")
    t.append("    ", style="")
    t.append("∞", style=f"bold {green}")
    t.append("   │\n", style=blue)
    t.append("  ╰──╮────────╯\n", style=blue)
    t.append("     ╰──\n", style=blue)
    return t


def _collect_skills() -> list[tuple[str, str]]:
    """Return (name, description) for all discovered skills."""
    try:
        from dcoder.skills.registry import SkillRegistry

        registry = SkillRegistry.get_instance()
        registry.discover_skills()
        return sorted(
            [(meta["name"], meta.get("description", "")) for meta in registry._skills.values()],
            key=lambda x: x[0],
        )
    except Exception:
        logger.debug("Could not discover skills for welcome banner", exc_info=True)
        return []


def _collect_subagents() -> list[tuple[str, str]]:
    """Return (name, description) for all loaded subagents."""
    try:
        from dcoder.subagents import get_built_in_subagents, list_subagents

        seen: dict[str, str] = {}
        for meta in get_built_in_subagents():
            seen[meta["name"]] = meta.get("description", "")
        for meta in list_subagents():
            seen[meta["name"]] = meta.get("description", "")
        return sorted(seen.items(), key=lambda x: x[0])
    except Exception:
        logger.debug("Could not discover subagents for welcome banner", exc_info=True)
        return []


def _truncate_to_width(
    names: list[str], max_chars: int, max_items: int,
) -> tuple[list[str], int]:
    """Return (shown_names, remaining_count) fitting within both limits.

    Truncates by *item count* first (MAX_DISPLAY_ITEMS) then by cumulative
    *character width* so long agent names don't wrap the line.
    """
    candidates = names[:max_items]
    result: list[str] = []
    current_len = 0
    for name in candidates:
        sep = 2 if result else 0  # ", " separator
        if current_len + sep + len(name) > max_chars and result:
            break
        result.append(name)
        current_len += sep + len(name)
    remaining = len(names) - len(result)
    return result, remaining


# ── Left panel widget ─────────────────────────────────────────────


class _LeftPanel(Widget):
    """Reactive left panel: logo + version + project dir + status.

    The ``status`` reactive property drives the status indicator colour:
    ``"starting"`` → yellow dot, ``"connected"`` → green dot.
    """

    DEFAULT_CSS = """
    _LeftPanel {
        width: 38;
        height: auto;
        padding: 0 0 0 1;
    }
    """

    status: reactive[str] = reactive("starting")

    def render(self) -> ConsoleRenderable:
        """Build the full left-panel content."""
        from dcoder._version import __version__

        logo = _build_logo_pixels()

        text = Text()
        # Version
        text.append("  Version  ", style="dim")
        text.append(f"{__version__}\n", style="bold")
        # Project directory name (basename only)
        cwd = os.getcwd()
        dir_name = os.path.basename(cwd) or cwd
        text.append("  Project  ", style="dim")
        text.append(f"{dir_name}\n", style="")
        # Connection status
        text.append("  Status   ", style="dim")
        if self.status == "connected":
            text.append("● ", style="bold green")
            text.append("connected\n", style="green")
        else:
            text.append("● ", style="bold yellow")
            text.append("starting\n", style="yellow")

        return Group(logo, text)

    def watch_status(self, _old: str, _new: str) -> None:
        """Auto-refresh when status changes."""
        self.refresh()


# ── Main banner ───────────────────────────────────────────────────


class WelcomeBanner(Widget):
    """Two-panel welcome banner card shown on app startup.

    Left panel: TalkOps pixel logo, version, project dir, status.
    Right panel: prompt help, skills list, subagents list.

    The banner auto-dismisses on first user submission; no explicit
    dismiss button.
    """

    DEFAULT_CSS = """
    WelcomeBanner {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
        border: round $primary;
        border-title-color: $primary;
        border-title-style: bold;
        background: transparent;
    }

    WelcomeBanner Horizontal {
        width: 100%;
        height: auto;
    }

    WelcomeBanner #welcome-right {
        width: 1fr;
        height: auto;
        padding: 0 2 0 1;
        border-left: solid $primary;
    }
    """

    # Store item data for popup actions
    _skills_data: list[tuple[str, str]]
    _subagents_data: list[tuple[str, str]]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.border_title = "DCoder - DevOps Coding Agent by TalkOps.ai"
        self._skills_data = []
        self._subagents_data = []

    def compose(self) -> ComposeResult:
        # Collect data
        self._skills_data = _collect_skills()
        self._subagents_data = _collect_subagents()

        with Horizontal():
            yield _LeftPanel(id="welcome-left")
            # Use _ClickablePanel so @click actions resolve on the widget
            # that actually renders the text with clickable "…more" spans.
            yield _ClickablePanel(
                self._build_right_panel(),
                skills_data=self._skills_data,
                subagents_data=self._subagents_data,
                id="welcome-right",
            )

    # ── Public API ────────────────────────────────────────────────

    def set_connected(self) -> None:
        """Transition the status indicator to green 'connected'."""
        try:
            left = self.query_one(_LeftPanel)
            left.status = "connected"
        except Exception:
            logger.debug("Could not update banner status", exc_info=True)

    # ── Private builders ──────────────────────────────────────────

    def _build_right_panel(self) -> Text:
        """Prompt help + skills + subagents."""
        text = Text()

        # Quick-start help
        text.append("Type a prompt", style="bold")
        text.append(" or use ", style="dim")
        text.append("/help", style="bold cyan")
        text.append(" for commands.  ", style="dim")
        text.append("!cmd", style="bold green")
        text.append(" runs shell.\n", style="dim")

        # Skills section
        text.append("\n")
        text.append("Skills   ", style="bold #BB9AF7")
        if self._skills_data:
            names = [n for n, _ in self._skills_data]
            shown, remaining = _truncate_to_width(names, MAX_INLINE_CHARS, MAX_DISPLAY_ITEMS)
            text.append(", ".join(shown), style="#9ECE6A")
            if remaining:
                text.append("  ", style="")
                text.append(
                    f"…{remaining} more",
                    style=Style(
                        bold=True, underline=True, color="rgb(122,162,247)",
                        meta={"@click": "show_skills_popup()"},
                    ),
                )
        else:
            text.append("none discovered", style="dim italic")
        text.append("\n", style="")

        # Subagents section
        text.append("\n")
        text.append("Agents   ", style="bold #BB9AF7")
        if self._subagents_data:
            names = [n for n, _ in self._subagents_data]
            shown, remaining = _truncate_to_width(names, MAX_INLINE_CHARS, MAX_DISPLAY_ITEMS)
            text.append(", ".join(shown), style="#7AA2F7")
            if remaining:
                text.append("  ", style="")
                text.append(
                    f"…{remaining} more",
                    style=Style(
                        bold=True, underline=True, color="rgb(122,162,247)",
                        meta={"@click": "show_agents_popup()"},
                    ),
                )
        else:
            text.append("none loaded", style="dim italic")
        text.append("\n", style="")

        return text


class _ClickablePanel(Static):
    """Static widget that handles '…more' click actions.

    Textual dispatches @click actions from Rich text meta on the widget
    that *renders* the text.  Since the right panel text lives inside a
    Static child (not the parent WelcomeBanner), the action methods must
    be defined here so Textual can find them.
    """

    def __init__(
        self,
        content: ConsoleRenderable | str,
        *,
        skills_data: list[tuple[str, str]],
        subagents_data: list[tuple[str, str]],
        **kwargs: Any,
    ) -> None:
        super().__init__(content, **kwargs)
        self._skills_data = skills_data
        self._subagents_data = subagents_data

    async def action_show_skills_popup(self) -> None:
        """Push the skills detail popup."""
        from dcoder.ui.welcome_popup import WelcomeDetailPopup

        await self.app.push_screen(
            WelcomeDetailPopup(title="⚡ Discovered Skills", items=self._skills_data)
        )

    async def action_show_agents_popup(self) -> None:
        """Push the subagents detail popup."""
        from dcoder.ui.welcome_popup import WelcomeDetailPopup

        await self.app.push_screen(
            WelcomeDetailPopup(title="🤖 Loaded Subagents", items=self._subagents_data)
        )
