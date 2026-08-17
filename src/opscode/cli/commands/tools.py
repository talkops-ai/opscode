"""CLI commands for managing external tools."""

from __future__ import annotations

import argparse
import shutil
from typing import Any

from rich.console import Console
from rich.table import Table

from opscode.mcp.discovery import MCPDiscovery
from opscode.output import OutputFormat, write_json
from opscode.ui.theme import DC_GREEN, DC_MUTED, DC_RED, DC_TEAL

BUILTIN_TOOLS: list[dict[str, str]] = [
    {"name": "read_file", "category": "filesystem", "description": "Read contents from a file"},
    {"name": "write_file", "category": "filesystem", "description": "Write or overwrite file contents"},
    {"name": "edit_file", "category": "filesystem", "description": "Perform precise line/chunk replacements in a file"},
    {"name": "execute", "category": "shell", "description": "Execute shell commands in the workspace"},
    {"name": "grep", "category": "search", "description": "Search code files using ripgrep pattern matching"},
    {"name": "glob", "category": "search", "description": "Find files matching glob patterns"},
    {"name": "ls", "category": "filesystem", "description": "List contents of a directory"},
]


def run_tools_command(args: argparse.Namespace) -> int:
    """Dispatch `opscode tools` subcommands."""
    subcommand = getattr(args, "tools_command", None)
    output_format: OutputFormat = getattr(args, "output_format", "text")

    if subcommand == "install":
        return _run_install(output_format=output_format)
    return _run_list(output_format=output_format)


def _run_list(*, output_format: OutputFormat = "text") -> int:
    tools = list(BUILTIN_TOOLS)

    # Discover MCP tools
    discovery = MCPDiscovery()
    servers = discovery.discover()
    for s_name in servers:
        tools.append({
            "name": f"mcp:{s_name}",
            "category": "mcp",
            "description": f"MCP tools provided by server '{s_name}'",
        })

    if output_format == "json":
        write_json("tools list", tools)
        return 0

    console = Console()
    table = Table(title="Available Agent Tools", show_header=True, header_style=f"bold {DC_TEAL}")
    table.add_column("Tool Name", style="bold")
    table.add_column("Category")
    table.add_column("Description", style=DC_MUTED)

    for t in tools:
        table.add_row(t["name"], t["category"], t["description"])

    console.print(table)
    return 0


def _run_install(*, output_format: OutputFormat = "text") -> int:
    rg_path = shutil.which("rg")
    rg_installed = rg_path is not None

    data = {
        "tool": "ripgrep",
        "status": "ok" if rg_installed else "missing",
        "path": rg_path or "",
    }

    if output_format == "json":
        write_json("tools install", data)
        return 0

    if rg_installed:
        Console().print(f"[green]ripgrep is already installed at: {rg_path}[/green]")
    else:
        Console().print(
            "[yellow]ripgrep is not installed on your system PATH.[/yellow]\n"
            "Install it via package manager:\n"
            "  • macOS: brew install ripgrep\n"
            "  • Ubuntu/Debian: apt install ripgrep\n"
            "  • Windows: winget install BurntSushi.ripgrep.MSVC"
        )
    return 0
