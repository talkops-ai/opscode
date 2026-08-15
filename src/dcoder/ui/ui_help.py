"""Rich-rendered help screens for DCoder CLI commands and subcommands."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape

from dcoder._version import __version__
from dcoder.ui.theme import DC_MUTED, DC_TEAL

console = Console()

PRIMARY = DC_TEAL
MUTED = DC_MUTED
DOCS_URL = "https://dcoder.ai/docs"
_HELP_OPTION_LINE = "  -h, --help    Show this help message and exit"


def show_help() -> None:
    """Show top-level help information."""
    console.print()
    console.print(f"[bold {PRIMARY}]dcoder[/bold {PRIMARY}] v{__version__}")
    console.print()
    console.print(
        f"Docs: [link={DOCS_URL}]{DOCS_URL}[/link]",
        style=MUTED,
    )
    console.print()
    console.print("[bold]Usage:[/bold]", style=PRIMARY)
    console.print("  dcoder [OPTIONS]                           Start interactive session")
    console.print("  dcoder agents <list|reset>                 Manage agents")
    console.print("  dcoder skills <list|info|trust>            Manage agent skills")
    console.print("  dcoder plugin <list|install|uninstall>     Manage plugins")
    console.print("  dcoder threads <list|delete>               Manage conversation threads")
    console.print("  dcoder mcp <config|login|list>             Manage MCP servers")
    console.print("  dcoder config [get <key>|set|path]         Inspect configuration")
    console.print("  dcoder auth <list|set|remove|status|path>  Manage provider credentials")
    console.print("  dcoder doctor                              Print install diagnostics")
    console.print("  dcoder tools <list|install>                Manage external tools")
    console.print()

    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  -r, --resume [ID]          Resume thread: -r for most recent, -r ID for specific")
    console.print("  -a, --agent NAME           Agent to use (default: dcoder)")
    console.print("  -M, --model MODEL          Model to use (e.g., anthropic:claude-opus-4-8, gpt-5.5)")
    console.print("  --model-params JSON        Extra model kwargs (e.g., '{\"temperature\": 0.7}')")
    console.print("  --max-retries N            Override max retries for transient model errors")
    console.print("  --profile-override JSON    Override model profile fields as JSON")
    console.print("  --default-model [MODEL]    Set or show the default model for future launches")
    console.print("  --clear-default-model      Clear the configured default model")
    console.print("  -m, --message TEXT         Initial prompt to auto-submit on start")
    console.print("  -s, --skill NAME           Invoke a skill when the session starts")
    console.print("  --startup-cmd CMD          Shell command to run at startup, before first prompt")
    console.print("  -y, --auto-approve         Enable classifier-backed Auto mode")
    console.print("  --yolo                     Run gated actions without review after acknowledgement")
    console.print("  --sandbox TYPE             Remote sandbox for execution (default: none)")
    console.print("  --sandbox-id ID            Attach to existing sandbox")
    console.print("  --sandbox-snapshot-name NAME Snapshot or blueprint name")
    console.print("  --sandbox-setup PATH       Setup script to run in sandbox after creation")
    console.print("  --mcp-config PATH          Load MCP tools from config JSON file")
    console.print("  --no-mcp                   Disable all MCP tool loading")
    console.print("  --trust-project-mcp        Trust project MCP configs without prompt")
    console.print("  --trust-project-hooks      Trust project .dcoder/hooks.json handlers")
    console.print("  --interpreter, --no-interpreter Enable/disable JS interpreter (`js_eval`)")
    console.print("  --interpreter-tools VALUE  PTC allowlist: 'safe', 'all', or comma-separated tools")
    console.print("  --allow-fs-tools LIST      Filesystem tool allowlist: 'all' or comma-separated tools")
    console.print("  -n, --non-interactive MSG  Run a single task non-interactively and exit")
    console.print("  -q, --quiet                Clean output for piping (requires -n or stdin)")
    console.print("  --no-stream                Buffer full response instead of streaming")
    console.print("  --max-turns N              Max agent turns before stopping (requires -n)")
    console.print("  --timeout SECONDS          Hard wall-clock timeout in seconds (requires -n)")
    console.print("  --goal TEXT                Draft goal criteria; review, then run accepted goal")
    console.print("  --rubric TEXT|@PATH        Acceptance criteria to grade against (requires -n)")
    console.print("  --rubric-model MODEL       Model the rubric grader uses")
    console.print("  --rubric-max-iterations N  Override grader iterations per rubric attempt")
    console.print("  --recursion-limit N        Override graph step budget (default: 2000)")
    console.print("  --stdin                    Read input from stdin explicitly")
    console.print("  --json                     Emit machine-readable JSON for commands")
    console.print("  -S, --shell-allow-list CMDS Comma-separated cmds, 'recommended', or 'all'")
    console.print("  -v, --version              Show dcoder version")
    console.print("  -h, --help                 Show this help message and exit")
    console.print()

    console.print("[bold]Non-Interactive Mode Examples:[/bold]", style=PRIMARY)
    console.print("  dcoder -n 'Plan terraform deployment'           # Headless task execution", style=MUTED)
    console.print("  dcoder -n 'List files' -S recommended           # Safe shell commands", style=MUTED)
    console.print("  dcoder -n 'Search logs' -S ls,cat,grep -q       # Quiet piping mode", style=MUTED)
    console.print("  cat prompt.txt | dcoder --stdin -q              # Read from stdin", style=MUTED)
    console.print()


def show_agents_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder agents <command> [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("[bold]Commands:[/bold]", style=PRIMARY)
    console.print("  list, ls    List all available agents")
    console.print("  reset       Reset an agent's prompt to default")
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --json      Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_list_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder agents list [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("List all configured and built-in agents.", style=MUTED)
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --json      Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_reset_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder agents reset --agent NAME [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("Reset an agent's prompt to default or copy from another agent.", style=MUTED)
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --agent NAME     Name of agent to reset (required)")
    console.print("  --target NAME    Copy prompt from another agent")
    console.print("  --dry-run        Show changes without applying")
    console.print("  --json           Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_skills_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder skills <command> [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("[bold]Commands:[/bold]", style=PRIMARY)
    console.print("  list, ls    List all discovered skills")
    console.print("  info NAME   Show details for a specific skill")
    console.print("  trust NAME  Trust a skill directory")
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --json      Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_skills_list_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder skills list [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("List skills discovered from user, project, and built-in locations.", style=MUTED)
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --json      Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_skills_info_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder skills info NAME [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("Show description, metadata, and instructions for a skill.", style=MUTED)
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --json      Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_skills_trust_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder skills trust NAME [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("Grant execution trust to a local or project skill directory.", style=MUTED)
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --path PATH Explicit path to skill directory")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_plugins_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder plugin <command> [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("[bold]Commands:[/bold]", style=PRIMARY)
    console.print("  list, ls        List installed and available plugins")
    console.print("  install ID      Install a plugin from marketplace or source")
    console.print("  uninstall ID    Uninstall a plugin")
    console.print("  enable ID       Enable an installed plugin")
    console.print("  disable ID      Disable an installed plugin")
    console.print("  marketplace     Manage plugin marketplace sources")
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --json          Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_config_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder config [get <key>|set <key> <value>|path] [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("Inspect or update DCoder configuration values.", style=MUTED)
    console.print()
    console.print("[bold]Commands:[/bold]", style=PRIMARY)
    console.print("  get <key|section>  Show effective value and source for an option or section")
    console.print("  set <key> <value>  Update a configuration setting in config.toml")
    console.print("  path               Print configuration file locations")
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  -v, --verbose, --all Show full descriptions and sources")
    console.print("  --json               Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_auth_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder auth <command> [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("Manage stored LLM provider credentials.", style=MUTED)
    console.print()
    console.print("[bold]Commands:[/bold]", style=PRIMARY)
    console.print("  list, ls           List providers and authentication status")
    console.print("  set <provider>     Store API key for a provider (read from stdin or --from-env)")
    console.print("  remove <provider>  Remove stored credentials (aliases: rm, delete)")
    console.print("  status <provider>  Show credential resolution source for a provider")
    console.print("  path               Print path to auth.json credential file")
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --from-env VAR     Copy key from an existing environment variable")
    console.print("  --json             Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_threads_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder threads <command> [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("Manage conversation threads and checkpoints.", style=MUTED)
    console.print()
    console.print("[bold]Commands:[/bold]", style=PRIMARY)
    console.print("  list, ls          List recent conversation threads")
    console.print("  delete <thread_id> Delete a thread and its history")
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --json            Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_threads_list_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder threads list [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --agent NAME      Filter by agent name")
    console.print("  -n, --limit N     Max threads to display (default: 20)")
    console.print("  --sort {created,updated} Sort order")
    console.print("  --branch NAME     Filter by git branch")
    console.print("  --cwd [PATH]      Filter by working directory")
    console.print("  -v, --verbose     Show detailed columns (branch, prompt)")
    console.print("  -r, --relative    Show relative timestamps (e.g., 5m ago)")
    console.print("  --json            Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_threads_delete_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder threads delete <thread_id> [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --dry-run   Show what would be deleted without making changes")
    console.print("  --json      Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_doctor_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder doctor [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("Print install health, dependencies, and environment diagnostics.", style=MUTED)
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --json      Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_tools_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder tools <command> [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("Manage external tools available to the agent.", style=MUTED)
    console.print()
    console.print("[bold]Commands:[/bold]", style=PRIMARY)
    console.print("  list        List available built-in and MCP tools")
    console.print("  install     Install or verify managed tools (e.g. ripgrep)")
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --json      Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_tools_list_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder tools list [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("List all tools exposed to the agent model.", style=MUTED)
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --json      Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_tools_install_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder tools install [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("Install or verify external dependencies (ripgrep).", style=MUTED)
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --json      Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_mcp_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder mcp <command> [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("Manage Model Context Protocol (MCP) servers and tools.", style=MUTED)
    console.print()
    console.print("[bold]Commands:[/bold]", style=PRIMARY)
    console.print("  config      Show MCP configuration discovery paths and servers")
    console.print("  login NAME  Run OAuth login flow for a remote MCP server")
    console.print("  list        List configured MCP servers and tool count")
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --json      Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_mcp_config_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder mcp config [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("Show MCP configuration file resolution paths and loaded servers.", style=MUTED)
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --json      Emit machine-readable JSON output")
    console.print(_HELP_OPTION_LINE)
    console.print()


def show_mcp_login_help() -> None:
    console.print()
    console.print("[bold]Usage:[/bold] dcoder mcp login <server> [OPTIONS]", style=PRIMARY)
    console.print()
    console.print("Initiate OAuth authentication with a remote MCP server.", style=MUTED)
    console.print()
    console.print("[bold]Options:[/bold]", style=PRIMARY)
    console.print("  --mcp-config PATH Explicit path to MCP config file")
    console.print(_HELP_OPTION_LINE)
    console.print()
