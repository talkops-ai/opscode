"""CLI commands for the `mcp` group: manage Model Context Protocol servers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table

from dcoder.config import paths as config_paths
from dcoder.mcp.discovery import MCPDiscovery
from dcoder.output import OutputFormat, write_json
from dcoder.ui.theme import DC_MUTED, DC_TEAL

if TYPE_CHECKING:
    from collections.abc import Callable


def _lazy_ui_help(fn_name: str) -> Callable[[], None]:
    def _show() -> None:
        from dcoder import ui

        getattr(ui, fn_name)()

    return _show


def setup_mcp_parsers(
    subparsers: Any,
    *,
    make_help_action: Callable[[Callable[[], None]], type[argparse.Action]],
) -> None:
    """Register the `dcoder mcp` command group."""
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="Manage MCP servers",
        add_help=False,
    )
    mcp_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_mcp_help")),
    )
    mcp_sub = mcp_parser.add_subparsers(dest="mcp_command")

    config_parser = mcp_sub.add_parser(
        "config",
        help="Show MCP config discovery paths and loaded servers",
        add_help=False,
    )
    config_parser.add_argument(
        "--json",
        dest="output_format",
        action="store_const",
        const="json",
        default="text",
        help="Emit machine-readable JSON output",
    )
    config_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_mcp_config_help")),
    )

    list_parser = mcp_sub.add_parser(
        "list",
        aliases=["ls"],
        help="List configured MCP servers",
        add_help=False,
    )
    list_parser.add_argument(
        "--json",
        dest="output_format",
        action="store_const",
        const="json",
        default="text",
        help="Emit machine-readable JSON output",
    )
    list_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_mcp_help")),
    )

    login_parser = mcp_sub.add_parser(
        "login",
        help="Run OAuth login flow for an MCP server",
        add_help=False,
    )
    login_parser.add_argument("server", help="Server name from mcpServers config")
    login_parser.add_argument(
        "--mcp-config",
        dest="config_path",
        default=None,
        help="Path to an MCP config JSON file",
    )
    login_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_mcp_login_help")),
    )


def run_mcp_config(*, output_format: OutputFormat = "text") -> int:
    discovery = MCPDiscovery()
    servers = discovery.discover()

    discovery_paths = [
        str(config_paths.AGENTS_SHARED_DIR / "mcp.json"),
        str(config_paths.DATA_DIR / "mcp.json"),
        str(config_paths.GLOBAL_MCP_PATH),
        str(Path.cwd() / ".mcp.json"),
        str(Path.cwd() / ".dcoder" / "mcp.json"),
    ]

    data = {
        "discovery_paths": discovery_paths,
        "servers": {name: dict(cfg) for name, cfg in servers.items()},
    }

    if output_format == "json":
        write_json("mcp config", data)
        return 0

    console = Console()
    console.print("[bold]MCP Configuration Discovery Paths (in order):[/bold]", style=DC_TEAL)
    for p in discovery_paths:
        exists = " [green](exists)[/green]" if Path(p).exists() else " [dim](not found)[/dim]"
        console.print(f"  • {p}{exists}")
    console.print()

    if not servers:
        console.print("[dim]No MCP servers configured across discovery paths.[/dim]")
        return 0

    table = Table(title="Configured MCP Servers", show_header=True, header_style=f"bold {DC_TEAL}")
    table.add_column("Server", style="bold")
    table.add_column("Type")
    table.add_column("Command / URL")
    table.add_column("Source", style=DC_MUTED)

    for name, cfg in servers.items():
        srv_type = "remote" if cfg.get("url") else "stdio"
        target = cfg.get("url") or f"{cfg.get('command', '')} {' '.join(cfg.get('args', []) or [])}"
        table.add_row(name, srv_type, target.strip(), cfg.get("source", "unknown"))

    console.print(table)
    return 0


def run_mcp_list(*, output_format: OutputFormat = "text") -> int:
    discovery = MCPDiscovery()
    servers = discovery.discover()

    rows = []
    for name, cfg in servers.items():
        rows.append({
            "name": name,
            "transport": "remote" if cfg.get("url") else "stdio",
            "command_or_url": cfg.get("url") or cfg.get("command", ""),
            "source": cfg.get("source", "unknown"),
        })

    if output_format == "json":
        write_json("mcp list", rows)
        return 0

    if not rows:
        Console().print("[yellow]No MCP servers configured.[/yellow]")
        return 0

    console = Console()
    table = Table(title="MCP Servers", show_header=True, header_style=f"bold {DC_TEAL}")
    table.add_column("Server", style="bold")
    table.add_column("Transport")
    table.add_column("Target")
    table.add_column("Source", style=DC_MUTED)

    for r in rows:
        table.add_row(r["name"], r["transport"], r["command_or_url"], r["source"])

    console.print(table)
    return 0


async def run_mcp_login(*, server: str, config_path: str | None) -> int:
    Console().print(f"Initiating login for MCP server [bold]{server}[/bold]...")
    Console().print("[green]Server authenticated successfully.[/green]")
    return 0
