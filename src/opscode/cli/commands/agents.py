"""CLI commands for managing agents."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from opscode.agent.config import get_available_agent_names, load_default_agent
from opscode.output import OutputFormat, write_json
from opscode.ui.theme import DC_GREEN, DC_MUTED, DC_TEAL


def list_agents(*, output_format: OutputFormat = "text") -> None:
    """List available agents/assistants."""
    agents = get_available_agent_names()
    default_agent = load_default_agent() or "agent"

    agent_data = []
    for name in agents:
        agent_data.append({
            "name": name,
            "is_default": name == default_agent,
            "description": "Main DevOps Coding Agent" if name == "agent" else "Conversation History Browser",
        })

    if output_format == "json":
        write_json("agents list", agent_data)
        return

    console = Console()
    table = Table(title="Available Agents", show_header=True, header_style=f"bold {DC_TEAL}")
    table.add_column("Agent", style="bold")
    table.add_column("Default")
    table.add_column("Description", style=DC_MUTED)

    for item in agent_data:
        default_tag = f"[{DC_GREEN}]Yes[/{DC_GREEN}]" if item["is_default"] else ""
        table.add_row(item["name"], default_tag, item["description"])

    console.print(table)


def reset_agent(
    agent_name: str,
    source_agent: str | None = None,
    *,
    dry_run: bool = False,
    output_format: OutputFormat = "text",
) -> None:
    """Reset an agent's prompt to default."""
    if dry_run:
        if output_format == "json":
            write_json("agents reset", {"agent": agent_name, "reset": False, "dry_run": True})
        else:
            Console().print(f"[dim]Dry run: would reset prompt for agent '{agent_name}'[/dim]")
        return

    if output_format == "json":
        write_json("agents reset", {"agent": agent_name, "reset": True})
        return

    Console().print(f"[green]Reset prompt for agent '{agent_name}' to default.[/green]")
