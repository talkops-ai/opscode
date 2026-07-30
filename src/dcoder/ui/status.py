"""Status bar widget for the DCoder TUI.

Shows agent status with animated spinner, git branch, input mode indicator,
token counts, and session timer.  No emoji — uses text labels and styled
separators for a clean, terminal-native aesthetic.

Architecture note:
    The spinner only animates when ``_status`` indicates active work
    (``Thinking...``, ``Running tool:``, ``Connecting...``).  When idle,
    the bar renders once and stops the ticker to save CPU.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.widgets import Static

if TYPE_CHECKING:
    from dcoder.ui.textual_adapter import SessionStats

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# Status values that trigger spinner animation
_ANIMATING_STATUSES = frozenset({
    "Thinking...",
    "Connecting...",
})


class StatusBar(Static):
    """Bottom status bar showing agent status, repository address, branch, model and thinking level."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $foreground;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self._status: str = "Ready"
        self._model: str = ""
        self._effort: str = ""
        self._approval_mode: str = "manual"
        self._mode: str = "normal"
        self._cwd: str = os.getcwd()
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._request_count: int = 0
        self._start_time: float = time.time()
        self._spinner_idx: int = 0
        self._branch: str = self._detect_git_branch()
        self._queued_count: int = 0
        self._render_bar()

    def on_mount(self) -> None:
        """Start periodic tick for spinner animation."""
        self.set_interval(0.1, self._tick)

    def on_click(self, event: Any) -> None:
        """Open model & effort selector when clicking the status bar."""
        event.stop()
        app_obj = getattr(self, "app", None)
        if app_obj and hasattr(app_obj, "_show_model_selector"):
            app_obj.run_worker(app_obj._show_model_selector())

    def _tick(self) -> None:
        """Advance spinner only when animating."""
        if self._is_animating():
            self._spinner_idx += 1
            self._render_bar()

    def _is_animating(self) -> bool:
        """Whether the status bar should animate the spinner."""
        return (
            self._status in _ANIMATING_STATUSES
            or self._status.startswith("Running tool:")
        )

    def _detect_git_branch(self) -> str:
        """Read git branch from .git/HEAD."""
        try:
            head_path = os.path.join(".git", "HEAD")
            if os.path.exists(head_path):
                with open(head_path, "r", encoding="utf-8") as f:
                    ref = f.read().strip()
                    if ref.startswith("ref: refs/heads/"):
                        return ref.replace("ref: refs/heads/", "")
        except Exception:
            pass
        return ""

    def _format_cwd(self, cwd_path: str = "") -> str:
        from pathlib import Path
        path = Path(cwd_path or self._cwd or os.getcwd())
        try:
            home = Path.home()
            if path.is_relative_to(home):
                return "~/" + path.relative_to(home).as_posix()
        except (ValueError, RuntimeError):
            pass
        return str(path)

    # ── Public API ──────────────────────────────────────

    def set_status(self, status: str) -> None:
        """Update the status message."""
        self._status = status
        self._render_bar()

    def set_mode(self, mode: str) -> None:
        """Update the input mode indicator."""
        self._mode = mode
        self._render_bar()

    def set_approval_mode(self, mode: str) -> None:
        """Set approval mode (manual, auto, yolo)."""
        self._approval_mode = mode if mode in {"manual", "auto", "yolo"} else "manual"
        self._render_bar()

    def set_model(self, model: str, effort: str | None = None) -> None:
        """Set the displayed model spec and reasoning effort."""
        self._model = model
        if effort is not None:
            self._effort = effort.strip("()") if effort else ""
        self._render_bar()

    def set_cwd(self, cwd: str) -> None:
        """Set current working directory display."""
        self._cwd = cwd
        self._render_bar()

    def set_branch(self, branch: str) -> None:
        """Set git branch display."""
        self._branch = branch
        self._render_bar()

    def set_queued_count(self, count: int) -> None:
        """Update the queued message count."""
        self._queued_count = count
        self._render_bar()

    def update_stats(self, stats: Any) -> None:
        """Update token counts and model from SessionStats."""
        self._input_tokens = stats.input_tokens
        self._output_tokens = stats.output_tokens
        self._request_count = stats.request_count
        if getattr(stats, "model", None):
            self._model = stats.model
        self._render_bar()

    def refresh_branch(self) -> None:
        """Re-detect git branch (e.g. after shell command)."""
        self._branch = self._detect_git_branch()
        self._render_bar()

    # ── Rendering ───────────────────────────────────────

    def _render_bar(self) -> None:
        """Compose and update the status bar text matching dcode layout 1:1."""
        full_text = Text()

        # 1. Approval mode pill (manual / auto / yolo)
        pill_mode = self._approval_mode if self._approval_mode in {"manual", "auto", "yolo"} else "manual"
        pill_style = {
            "manual": "bold black on dark_orange",
            "auto": "bold black on green",
            "yolo": "bold white on red",
        }.get(pill_mode, "bold black on dark_orange")

        full_text.append(f" {pill_mode} ", style=pill_style)
        full_text.append(" ")

        # 2. CWD & Branch
        cwd_str = self._format_cwd(self._cwd)
        branch_str = f" ↗ {self._branch}" if self._branch else ""

        # Animated or custom status message if non-default
        if self._is_animating():
            spinner = SPINNER_FRAMES[self._spinner_idx % len(SPINNER_FRAMES)]
            full_text.append(f"{spinner} {self._status} ", style="bold yellow")
        elif self._status and self._status not in ("Ready", "manual", "auto"):
            full_text.append(f"● {self._status} ", style="bold cyan")

        if self._queued_count > 0:
            full_text.append(f"{self._queued_count} queued ", style="yellow")

        full_text.append(f"{cwd_str}{branch_str}", style="dim")

        # 3. Model & Thinking / Reasoning effort on the right
        model_str = self._model
        if self._effort:
            model_str = f"{model_str} {self._effort}" if model_str else self._effort

        if model_str:
            width = self.size.width if self.size.width > 0 else 100
            left_len = full_text.cell_len
            right_len = len(model_str)
            padding_len = max(1, width - left_len - right_len - 2)
            full_text.append(" " * padding_len)
            full_text.append(model_str, style="dim")

        self.update(full_text)


def _format_count(n: int) -> str:
    """Format a token count for display (e.g. 1.2k, 15.3k)."""
    if n < 1000:
        return str(n)
    if n < 100_000:
        return f"{n / 1000:.1f}k"
    return f"{n / 1000:.0f}k"
