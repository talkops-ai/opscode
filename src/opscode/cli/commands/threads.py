"""CLI commands for managing conversation threads and checkpoints."""

from __future__ import annotations

import argparse
import asyncio
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.markup import escape as escape_markup
from rich.table import Table

from opscode.output import OutputFormat, write_json
from opscode.state.session import (
    delete_thread,
    format_relative_timestamp,
    format_timestamp,
    list_threads,
)
from opscode.ui.theme import DC_MUTED, DC_TEAL


async def list_threads_command(
    agent_name: str | None = None,
    limit: int | None = None,
    sort_by: str | None = None,
    branch: str | None = None,
    cwd: str | None = None,
    verbose: bool = False,
    relative: bool | None = None,
    *,
    output_format: OutputFormat = "text",
) -> None:
    """CLI handler for `opscode threads list`."""
    sort_by = sort_by or "updated"
    limit = max(1, limit) if limit is not None else 20

    threads = await list_threads(
        agent_name=agent_name,
        limit=limit,
        include_message_count=True,
        sort_by=sort_by,
        branch=branch,
        cwd=cwd,
    )

    if output_format == "json":
        write_json("threads list", [dict(t) for t in threads])
        return

    console = Console()
    if not threads:
        console.print("[yellow]No conversation threads found.[/yellow]")
        console.print("[dim]Start a conversation with: opscode[/dim]")
        return

    fmt_ts = format_relative_timestamp if relative else format_timestamp
    sort_label = "created" if sort_by == "created" else "updated"
    title = f"Recent Threads (last {limit}, by {sort_label})"

    table = Table(title=title, show_header=True, header_style=f"bold {DC_TEAL}")
    table.add_column("Thread ID", style="bold")
    table.add_column("Agent")
    table.add_column("Messages", justify="right")
    if verbose:
        table.add_column("Created")
    table.add_column("Updated" if sort_by == "updated" else "Last Used")
    if verbose:
        table.add_column("Branch")
        table.add_column("CWD", style=DC_MUTED)

    for t in threads:
        tid = t.get("thread_id", "")
        agent = t.get("agent_name", "opscode")
        msg_count = str(t.get("message_count", 0))
        updated = fmt_ts(t.get("updated_at", ""))
        created = fmt_ts(t.get("created_at", ""))

        if verbose:
            br = t.get("git_branch") or "-"
            cwd_str = t.get("cwd") or "-"
            table.add_row(tid, agent, msg_count, created, updated, br, cwd_str)
        else:
            table.add_row(tid, agent, msg_count, updated)

    console.print(table)


async def delete_thread_command(
    thread_id: str,
    *,
    dry_run: bool = False,
    output_format: OutputFormat = "text",
) -> None:
    """CLI handler for `opscode threads delete <thread_id>`."""
    if dry_run:
        if output_format == "json":
            write_json("threads delete", {"thread_id": thread_id, "deleted": False, "dry_run": True})
        else:
            Console().print(f"[dim]Dry run: would delete thread {thread_id}[/dim]")
        return

    success = await delete_thread(thread_id)
    if output_format == "json":
        write_json("threads delete", {"thread_id": thread_id, "deleted": success})
        return

    if success:
        Console().print(f"[green]Deleted thread {thread_id}[/green]")
    else:
        Console(stderr=True).print(f"[yellow]Thread {thread_id} not found or already deleted.[/yellow]")
