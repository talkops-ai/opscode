"""Diff display widget for the DCoder TUI.

Renders unified diffs with theme tokens and section collapsing for unchanged lines.
"""

from __future__ import annotations

import re
from rich.text import Text

_HUNK_RE = re.compile(r"@@ -(\d+)(?:,\d+)? \+(\d+)")


def compose_diff_lines(
    diff: str,
    max_lines: int | None = 150,
    add_style: str = "green",
    del_style: str = "red",
    header_style: str = "cyan",
    hunk_style: str = "yellow",
) -> Text:
    """Compose a Rich Text representation of a unified diff with context line collapsing.

    Args:
        diff: Unified diff string.
        max_lines: Max line limit for render.
        add_style: Style for additions (+).
        del_style: Style for deletions (-).
        header_style: Style for file headers (+++/---).
        hunk_style: Style for hunk headers (@@).
    """
    output = Text()
    lines = diff.splitlines()

    context_buf: list[str] = []

    def flush_context():
        nonlocal context_buf
        if not context_buf:
            return
        if len(context_buf) > 6:
            output.append(f"  {context_buf[0]}\n", style="dim")
            output.append(f"  ... ({len(context_buf) - 2} unchanged lines) ...\n", style="dim italic")
            output.append(f"  {context_buf[-1]}\n", style="dim")
        else:
            for ctx in context_buf:
                output.append(f"  {ctx}\n", style="dim")
        context_buf = []

    count = 0
    for line in lines:
        if max_lines is not None and count >= max_lines:
            flush_context()
            output.append(f"\n... ({len(lines) - count} lines truncated)\n", style="dim italic")
            break

        if line.startswith("+++") or line.startswith("---"):
            flush_context()
            output.append(f"{line}\n", style=f"bold {header_style}")
        elif line.startswith("+"):
            flush_context()
            output.append(f"{line}\n", style=f"bold {add_style}")
        elif line.startswith("-"):
            flush_context()
            output.append(f"{line}\n", style=f"bold {del_style}")
        elif _HUNK_RE.match(line):
            flush_context()
            output.append(f"{line}\n", style=f"bold {hunk_style}")
        else:
            context_buf.append(line)

        count += 1


    flush_context()
    return output
