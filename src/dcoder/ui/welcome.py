"""Welcome banner & first-run onboarding widget for DCoder TUI.

Displays compact welcome branding with tool detection and session metadata.
Matches dcode's Static-based banner with ``border: round`` styling.
"""

from __future__ import annotations

import os
import shutil
from typing import Any

from rich.text import Text
from textual.widgets import Static


class WelcomeBanner(Static):
    """Compact welcome banner card shown on app startup.

    Uses a single ``Static`` widget (no compose tree) for minimal DOM
    footprint — matching the dcode pattern.  The banner auto-dismisses
    on first user submission; no explicit dismiss button.
    """

    DEFAULT_CSS = """
    WelcomeBanner {
        padding: 1 2;
        margin: 1 0 1 0;
        border: round $primary;
        background: transparent;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        content = self._build_content()
        super().__init__(content, **kwargs)

    def _build_content(self) -> Text:
        """Build the banner content as Rich Text."""
        text = Text()

        from dcoder._version import __version__
        from dcoder.model.config import is_warning_suppressed

        # Title
        text.append("DCoder", style="bold cyan")
        text.append(" — DevOps Coding Agent", style="bold")
        text.append(f"  v{__version__}\n", style="dim")

        # Session metadata
        cwd = os.getcwd()
        text.append("  Directory  ", style="dim")
        text.append(f"{cwd}\n", style="")

        # Tool detection
        tools = self._detect_tools()
        detected = [name for name, ok in tools.items() if ok]
        missing = [
            name for name, ok in tools.items() if not ok and not is_warning_suppressed(name)
        ]

        text.append("  Tools      ", style="dim")
        if detected:
            text.append(", ".join(detected), style="green")
        if missing:
            if detected:
                text.append("  ", style="")
            text.append(f"({', '.join(missing)} not found)", style="dim red")
        text.append("\n", style="")

        # Quick start
        text.append("\n  ", style="")
        text.append("Type a prompt", style="bold")
        text.append(" or use ", style="dim")
        text.append("/help", style="bold cyan")
        text.append(" for commands.  ", style="dim")
        text.append("!cmd", style="bold green")
        text.append(" runs shell.", style="dim")

        return text

    @staticmethod
    def _detect_tools() -> dict[str, bool]:
        """Detect available DevOps CLI tools."""
        return {
            "terraform": shutil.which("terraform") is not None or shutil.which("tofu") is not None,
            "kubectl": shutil.which("kubectl") is not None,
            "helm": shutil.which("helm") is not None,
            "ansible": shutil.which("ansible") is not None,
            "docker": shutil.which("docker") is not None,
        }
