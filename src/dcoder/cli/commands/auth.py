"""CLI commands for the `auth` group: manage stored provider credentials."""

from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table

from dcoder.config.paths import GLOBAL_ENV_PATH, upsert_env_vars
from dcoder.model.config import get_credential_env_var, get_provider_display_name, has_provider_credentials
from dcoder.output import OutputFormat, write_json
from dcoder.ui.theme import DC_GREEN, DC_MUTED, DC_RED, DC_TEAL

if TYPE_CHECKING:
    from collections.abc import Callable

_KNOWN_PROVIDERS: tuple[str, ...] = (
    "google_genai",
    "openai",
    "anthropic",
    "groq",
    "deepseek",
    "openrouter",
    "azure_openai",
    "mistralai",
    "fireworks",
    "together",
    "xai",
    "cohere",
    "perplexity",
    "bedrock",
)


def _lazy_ui_help(fn_name: str) -> Callable[[], None]:
    def _show() -> None:
        from dcoder import ui

        getattr(ui, fn_name)()

    return _show


def setup_auth_parser(
    subparsers: Any,
    *,
    make_help_action: Callable[[Callable[[], None]], type[argparse.Action]],
) -> None:
    """Register the `dcoder auth` command group."""
    auth_parser = subparsers.add_parser(
        "auth",
        help="Manage stored model-provider credentials",
        add_help=False,
    )
    auth_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_auth_help")),
    )
    auth_sub = auth_parser.add_subparsers(dest="auth_command")

    list_parser = auth_sub.add_parser(
        "list",
        aliases=["ls"],
        help="List providers and their credential status",
        add_help=False,
    )
    list_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_auth_help")),
    )
    list_parser.add_argument(
        "--json",
        dest="output_format",
        action="store_const",
        const="json",
        default="text",
        help="Emit machine-readable JSON output",
    )

    set_parser = auth_sub.add_parser(
        "set",
        help="Store an API key for a provider (key read from stdin or --from-env)",
        add_help=False,
    )
    set_parser.add_argument("provider", help="Provider name (e.g. anthropic, openai)")
    set_parser.add_argument(
        "--from-env",
        dest="from_env",
        metavar="VAR",
        default=None,
        help="Copy the key from this environment variable instead of stdin",
    )
    set_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_auth_help")),
    )

    remove_parser = auth_sub.add_parser(
        "remove",
        aliases=["rm", "delete"],
        help="Remove a stored credential for a provider",
        add_help=False,
    )
    remove_parser.add_argument("provider", help="Provider name (e.g. anthropic, openai)")
    remove_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_auth_help")),
    )

    status_parser = auth_sub.add_parser(
        "status",
        help="Show the credential resolution source for one provider",
        add_help=False,
    )
    status_parser.add_argument(
        "provider",
        nargs="?",
        default=None,
        metavar="provider",
        help="Provider name (e.g. anthropic)",
    )
    status_parser.add_argument(
        "--json",
        dest="output_format",
        action="store_const",
        const="json",
        default="text",
        help="Emit machine-readable JSON output",
    )
    status_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_auth_help")),
    )

    path_parser = auth_sub.add_parser(
        "path",
        help="Print the resolved credentials file path",
        add_help=False,
    )
    path_parser.add_argument(
        "--json",
        dest="output_format",
        action="store_const",
        const="json",
        default="text",
        help="Emit machine-readable JSON output",
    )
    path_parser.add_argument(
        "-h",
        "--help",
        action=make_help_action(_lazy_ui_help("show_auth_help")),
    )


def run_auth_command(args: argparse.Namespace) -> int:
    """Dispatch a parsed `dcoder auth` invocation."""
    command = getattr(args, "auth_command", None)
    output_format: OutputFormat = getattr(args, "output_format", "text")

    if command in {"list", "ls"}:
        return _run_list(output_format=output_format)
    if command == "set":
        return _run_set(args.provider, from_env=args.from_env)
    if command in {"remove", "rm", "delete"}:
        return _run_remove(args.provider)
    if command == "status":
        return _run_status(getattr(args, "provider", None), output_format=output_format)
    if command == "path":
        return _run_path(output_format=output_format)

    from dcoder.ui.ui_help import show_auth_help

    show_auth_help()
    return 0


def _get_provider_auth_info(provider: str) -> dict[str, Any]:
    env_var = get_credential_env_var(provider)
    has_creds = has_provider_credentials(provider)
    env_val = os.environ.get(env_var) if env_var else None

    source = "missing"
    if env_val:
        source = f"env: {env_var}"
    elif has_creds:
        source = "stored"

    return {
        "provider": provider,
        "display_name": get_provider_display_name(provider),
        "configured": bool(has_creds),
        "source": source,
        "env_var": env_var,
    }


def _run_list(*, output_format: OutputFormat = "text") -> int:
    providers = [_get_provider_auth_info(p) for p in _KNOWN_PROVIDERS]

    if output_format == "json":
        write_json("auth list", providers)
        return 0

    console = Console()
    table = Table(title="Model Provider Credentials", show_header=True, header_style=f"bold {DC_TEAL}")
    table.add_column("Provider", style="bold")
    table.add_column("Status")
    table.add_column("Resolution Source", style=DC_MUTED)

    for p in providers:
        if p["configured"]:
            status_text = f"[{DC_GREEN}]Configured[/{DC_GREEN}]"
        else:
            status_text = f"[{DC_RED}]Missing[/{DC_RED}]"
        table.add_row(p["display_name"], status_text, p["source"])

    console.print(table)
    return 0


def _run_set(provider: str, *, from_env: str | None = None) -> int:
    console = Console(stderr=True)
    provider_norm = provider.lower().replace("-", "_")

    key: str | None = None
    if from_env:
        key = os.environ.get(from_env)
        if not key:
            console.print(f"[bold red]Error:[/bold red] Environment variable `{from_env}` is not set or empty.")
            return 1
    else:
        if sys.stdin.isatty():
            console.print(
                "[bold red]Error:[/bold red] Refusing to read API key from interactive terminal. "
                f"Pipe via stdin (`echo 'KEY' | dcoder auth set {provider}`) or use `--from-env VAR`."
            )
            return 2
        key = sys.stdin.read().strip()

    if not key:
        console.print("[bold red]Error:[/bold red] No API key provided.")
        return 1

    env_var = get_credential_env_var(provider_norm) or f"{provider_norm.upper()}_API_KEY"
    success = upsert_env_vars({env_var: key})
    if success:
        os.environ[env_var] = key
        Console().print(f"[green]Stored credentials for {get_provider_display_name(provider_norm)} ({env_var}).[/green]")
        return 0
    else:
        console.print(f"[bold red]Error:[/bold red] Failed to write credentials to {GLOBAL_ENV_PATH}.")
        return 1


def _run_remove(provider: str) -> int:
    provider_norm = provider.lower().replace("-", "_")
    env_var = get_credential_env_var(provider_norm) or f"{provider_norm.upper()}_API_KEY"

    if not GLOBAL_ENV_PATH.exists():
        Console().print(f"No stored credentials found for {provider_norm}.")
        return 0

    content = GLOBAL_ENV_PATH.read_text(encoding="utf-8")
    lines = content.splitlines()
    new_lines = [l for l in lines if not l.strip().startswith(f"{env_var}=") and not l.strip().startswith(f"export {env_var}=")]
    
    GLOBAL_ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.environ.pop(env_var, None)
    Console().print(f"[green]Removed stored credentials for {get_provider_display_name(provider_norm)}.[/green]")
    return 0


def _run_status(provider: str | None, *, output_format: OutputFormat = "text") -> int:
    if not provider:
        return _run_list(output_format=output_format)

    provider_norm = provider.lower().replace("-", "_")
    info = _get_provider_auth_info(provider_norm)

    if output_format == "json":
        write_json("auth status", info)
        return 0

    console = Console()
    status_badge = f"[{DC_GREEN}]Configured[/{DC_GREEN}]" if info["configured"] else f"[{DC_RED}]Missing[/{DC_RED}]"
    console.print(f"[bold]{info['display_name']}:[/bold] {status_badge} ({info['source']})")
    return 0


def _run_path(*, output_format: OutputFormat = "text") -> int:
    if output_format == "json":
        write_json("auth path", {"path": str(GLOBAL_ENV_PATH)})
        return 0

    Console().print(str(GLOBAL_ENV_PATH))
    return 0
