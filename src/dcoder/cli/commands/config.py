"""CLI commands for inspecting and editing DCoder configuration."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table

from dcoder.config.paths import CONFIG_PATH, DATA_DIR, GLOBAL_ENV_PATH, STATE_DIR
from dcoder.config.settings import settings
from dcoder.config.toml_config import _save_toml_field, read_config_toml
from dcoder.output import OutputFormat, write_json
from dcoder.ui.theme import DC_MUTED, DC_TEAL

if TYPE_CHECKING:
    from collections.abc import Callable


def _lazy_ui_help(fn_name: str) -> Callable[[], None]:
    def _show() -> None:
        from dcoder import ui

        getattr(ui, fn_name)()

    return _show


def setup_config_parser(
    subparsers: Any,
    *,
    make_help_action: Callable[[Callable[[], None]], type[argparse.Action]],
    add_output_args: Callable[[argparse.ArgumentParser], None] | None = None,
) -> None:
    """Register the `dcoder config` command group."""
    config_parser = subparsers.add_parser(
        "config",
        help="Inspect configuration options and their sources",
        add_help=False,
    )
    config_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_config_help")),
    )
    if add_output_args is not None:
        add_output_args(config_parser)
    else:
        config_parser.add_argument(
            "--json",
            dest="output_format",
            action="store_const",
            const="json",
            default="text",
            help="Emit machine-readable JSON output",
        )

    config_parser.add_argument(
        "-v",
        "--verbose",
        "--all",
        dest="verbose",
        action="store_true",
        help="Also show each option's description and where to set it",
    )
    config_sub = config_parser.add_subparsers(dest="config_command")

    get_parser = config_sub.add_parser(
        "get",
        help="Show the effective value and source for one option or section",
        add_help=False,
    )
    get_parser.add_argument("key", nargs="?", default=None, help="Option key (e.g. models.default)")
    if add_output_args is not None:
        add_output_args(get_parser)
    get_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_config_help")),
    )

    set_parser = config_sub.add_parser(
        "set",
        help="Update a configuration setting in config.toml",
        add_help=False,
    )
    set_parser.add_argument("key", help="Dotted config key (e.g. models.default or theme)")
    set_parser.add_argument("value", help="Value to set")
    set_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_config_help")),
    )

    path_parser = config_sub.add_parser(
        "path",
        help="Print configuration file locations",
        add_help=False,
    )
    if add_output_args is not None:
        add_output_args(path_parser)
    path_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_config_help")),
    )


def run_config_command(args: argparse.Namespace) -> int:
    """Dispatch `dcoder config` commands."""
    command = getattr(args, "config_command", None)
    output_format: OutputFormat = getattr(args, "output_format", "text")
    verbose: bool = getattr(args, "verbose", False)

    if command == "get":
        return _run_get(args.key, output_format=output_format)
    if command == "set":
        return _run_set(args.key, args.value)
    if command == "path":
        return _run_path(output_format=output_format)

    return _run_summary(verbose=verbose, output_format=output_format)


def _collect_config_items() -> list[dict[str, Any]]:
    toml_data = read_config_toml()
    items: list[dict[str, Any]] = [
        {
            "key": "models.default",
            "value": toml_data.get("models", {}).get("default") or getattr(settings, "model_name", None),
            "source": "config.toml" if toml_data.get("models", {}).get("default") else "runtime/default",
            "description": "Default LLM model identifier for sessions",
        },
        {
            "key": "models.recent",
            "value": toml_data.get("models", {}).get("recent"),
            "source": "config.toml" if toml_data.get("models", {}).get("recent") else "none",
            "description": "Most recently selected model",
        },
        {
            "key": "general.theme",
            "value": toml_data.get("general", {}).get("theme", "dcoder-dark"),
            "source": "config.toml" if "theme" in toml_data.get("general", {}) else "default",
            "description": "TUI theme palette name",
        },
        {
            "key": "runtime.recursion_limit",
            "value": getattr(settings, "recursion_limit", 2000),
            "source": "settings",
            "description": "LangGraph step execution budget",
        },
        {
            "key": "runtime.enable_interpreter",
            "value": getattr(settings, "enable_interpreter", True),
            "source": "settings",
            "description": "Enable JS interpreter middleware",
        },
        {
            "key": "runtime.enable_skills",
            "value": getattr(settings, "enable_skills", True),
            "source": "settings",
            "description": "Enable skill execution",
        },
        {
            "key": "permissions.auto_approve",
            "value": getattr(settings, "auto_approve", False),
            "source": "settings",
            "description": "Classifier-backed Auto approval mode",
        },
    ]
    return items


def _run_summary(*, verbose: bool = False, output_format: OutputFormat = "text") -> int:
    items = _collect_config_items()

    if output_format == "json":
        write_json("config", items)
        return 0

    console = Console()
    table = Table(title="DCoder Configuration", show_header=True, header_style=f"bold {DC_TEAL}")
    table.add_column("Option", style="bold")
    table.add_column("Effective Value")
    table.add_column("Source", style=DC_MUTED)
    if verbose:
        table.add_column("Description", style="dim")

    for item in items:
        val_str = str(item["value"]) if item["value"] is not None else "[dim]None[/dim]"
        if verbose:
            table.add_row(item["key"], val_str, item["source"], item["description"])
        else:
            table.add_row(item["key"], val_str, item["source"])

    console.print(table)
    return 0


def _run_get(key: str | None, *, output_format: OutputFormat = "text") -> int:
    items = _collect_config_items()
    if not key:
        return _run_summary(output_format=output_format)

    matched = [it for it in items if it["key"].lower().startswith(key.lower())]
    if not matched:
        Console(stderr=True).print(f"[bold yellow]No configuration option found matching:[/bold yellow] {key}")
        return 1

    if output_format == "json":
        write_json("config get", matched if len(matched) > 1 else matched[0])
        return 0

    console = Console()
    for item in matched:
        console.print(f"[bold]{item['key']}:[/bold] {item['value']} [dim]({item['source']})[/dim]")
    return 0


def _run_set(key: str, value: str) -> int:
    console = Console(stderr=True)
    if "." in key:
        section, field = key.split(".", 1)
    else:
        section, field = "general", key

    # Parse boolean / integer conversions if applicable
    parsed_val: Any = value
    if value.lower() in ("true", "yes"):
        parsed_val = True
    elif value.lower() in ("false", "no"):
        parsed_val = False
    elif value.isdigit():
        parsed_val = int(value)

    success = _save_toml_field(section, field, parsed_val)
    if success:
        Console().print(f"[green]Set [{section}].{field} = {parsed_val!r} in {CONFIG_PATH}[/green]")
        return 0
    else:
        console.print(f"[bold red]Error:[/bold red] Failed to save {key} to {CONFIG_PATH}")
        return 1


def _run_path(*, output_format: OutputFormat = "text") -> int:
    paths = {
        "config_toml": str(CONFIG_PATH),
        "env_file": str(GLOBAL_ENV_PATH),
        "data_dir": str(DATA_DIR),
        "state_dir": str(STATE_DIR),
    }
    if output_format == "json":
        write_json("config path", paths)
        return 0

    console = Console()
    console.print(f"[bold]Config TOML:[/bold] {CONFIG_PATH}")
    console.print(f"[bold]Environment:[/bold] {GLOBAL_ENV_PATH}")
    console.print(f"[bold]Data Dir:[/bold]    {DATA_DIR}")
    console.print(f"[bold]State Dir:[/bold]   {STATE_DIR}")
    return 0
