"""CLI commands for managing DCoder skills."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table

from dcoder.config.settings import settings
from dcoder.output import OutputFormat, write_json
from dcoder.skills.loader import list_skills
from dcoder.skills.trust import SkillTrustStore
from dcoder.ui.theme import DC_GREEN, DC_MUTED, DC_RED, DC_TEAL

if TYPE_CHECKING:
    from collections.abc import Callable


def _lazy_ui_help(fn_name: str) -> Callable[[], None]:
    def _show() -> None:
        from dcoder import ui

        getattr(ui, fn_name)()

    return _show


def setup_skills_parser(
    subparsers: Any,
    *,
    make_help_action: Callable[[Callable[[], None]], type[argparse.Action]],
    add_output_args: Callable[[argparse.ArgumentParser], None] | None = None,
) -> argparse.ArgumentParser:
    """Setup the skills subcommand parser with all its subcommands."""
    skills_parser = subparsers.add_parser(
        "skills",
        help="Manage agent skills",
        description="Manage agent skills — list, inspect, and trust skills.",
        add_help=False,
    )
    skills_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_skills_help")),
    )
    if add_output_args is not None:
        add_output_args(skills_parser)

    skills_subparsers = skills_parser.add_subparsers(dest="skills_command")

    # list / ls
    list_parser = skills_subparsers.add_parser(
        "list",
        aliases=["ls"],
        help="List all available skills",
        add_help=False,
    )
    if add_output_args is not None:
        add_output_args(list_parser)
    list_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_skills_list_help")),
    )

    # info
    info_parser = skills_subparsers.add_parser(
        "info",
        help="Show detailed information about a skill",
        add_help=False,
    )
    info_parser.add_argument("name", help="Name of skill to inspect")
    if add_output_args is not None:
        add_output_args(info_parser)
    info_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_skills_info_help")),
    )

    # trust
    trust_parser = skills_subparsers.add_parser(
        "trust",
        help="Grant execution trust to a skill directory",
        add_help=False,
    )
    trust_parser.add_argument("name", help="Name of skill to trust")
    trust_parser.add_argument("--path", default=None, help="Explicit path to skill directory")
    trust_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_skills_trust_help")),
    )

    return skills_parser


def list_skills_command() -> list[dict[str, str]]:
    """List all discovered skills and their trust status."""
    discovered = list_skills(project_root=settings.project_root)
    store = SkillTrustStore()

    results = []
    for skill in discovered:
        path = Path(skill["path"])
        trusted = store.is_trusted(skill["name"], path)
        results.append({
            "name": skill["name"],
            "description": skill.get("description", ""),
            "source": skill["source"],
            "path": str(path),
            "trusted": "Yes" if trusted else "No",
        })
    return results


def trust_skill_command(name: str, path_str: str) -> bool:
    """Trust a skill directory."""
    path = Path(path_str)
    if not path.exists():
        return False
    store = SkillTrustStore()
    store.trust_skill(name, path)
    return True


def execute_skills_command(args: argparse.Namespace) -> int:
    """Dispatch parsed `dcoder skills` command."""
    command = getattr(args, "skills_command", None)
    output_format: OutputFormat = getattr(args, "output_format", "text")

    if command in {"list", "ls"} or command is None:
        skills = list_skills_command()
        if output_format == "json":
            write_json("skills list", skills)
            return 0

        if not skills:
            Console().print("[yellow]No skills discovered.[/yellow]")
            return 0

        table = Table(title="Discovered Skills", show_header=True, header_style=f"bold {DC_TEAL}")
        table.add_column("Skill", style="bold")
        table.add_column("Source")
        table.add_column("Trusted")
        table.add_column("Description", style=DC_MUTED)

        for s in skills:
            trust_style = DC_GREEN if s["trusted"] == "Yes" else DC_RED
            table.add_row(s["name"], s["source"], f"[{trust_style}]{s['trusted']}[/{trust_style}]", s["description"])

        Console().print(table)
        return 0

    if command == "info":
        skill_name = args.name
        discovered = list_skills(project_root=settings.project_root)
        matched = next((s for s in discovered if s["name"].lower() == skill_name.lower()), None)
        if not matched:
            Console(stderr=True).print(f"[bold red]Error:[/bold red] Skill '{skill_name}' not found.")
            return 1

        skill_path = Path(matched["path"])
        skill_md = skill_path / "SKILL.md"
        instructions = ""
        if skill_md.is_file():
            instructions = skill_md.read_text(encoding="utf-8")

        data = {
            "name": matched["name"],
            "description": matched.get("description", ""),
            "source": matched["source"],
            "path": str(matched["path"]),
            "instructions": instructions,
        }
        if output_format == "json":
            write_json("skills info", data)
            return 0

        console = Console()
        console.print(f"[bold {DC_TEAL}]{data['name']}[/bold {DC_TEAL}] [dim]({data['source']})[/dim]")
        console.print(f"[bold]Path:[/bold] {data['path']}")
        console.print(f"[bold]Description:[/bold] {data['description']}")
        if data["instructions"]:
            console.print()
            console.print("[bold]Instructions:[/bold]")
            console.print(data["instructions"][:500] + ("..." if len(data["instructions"]) > 500 else ""))
        return 0

    if command == "trust":
        skill_name = args.name
        target_path = args.path
        if not target_path:
            discovered = list_skills(project_root=settings.project_root)
            matched = next((s for s in discovered if s["name"].lower() == skill_name.lower()), None)
            if not matched:
                Console(stderr=True).print(f"[bold red]Error:[/bold red] Skill '{skill_name}' not found. Specify --path.")
                return 1
            target_path = matched["path"]

        success = trust_skill_command(skill_name, target_path)
        if success:
            Console().print(f"[green]Skill '{skill_name}' at '{target_path}' is now trusted.[/green]")
            return 0
        else:
            Console(stderr=True).print(f"[bold red]Error:[/bold red] Path '{target_path}' does not exist.")
            return 1

    from dcoder.ui.ui_help import show_skills_help

    show_skills_help()
    return 0
