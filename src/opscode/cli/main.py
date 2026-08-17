"""OpsCode CLI entry point and argument parser.

Routes between interactive TUI mode (default), subcommands (agents, skills,
mcp, plugin, config, auth, threads, doctor, tools), and non-interactive headless
mode (`-n` / positional prompt / piped stdin).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from opscode.approval_mode import ApprovalMode
from opscode.output import OutputFormat, add_json_output_arg

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


# ── Argument Types ───────────────────────────────────────


def positive_int(value: str) -> int:
    """Validate positive integer arguments (> 0)."""
    try:
        ivalue = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a valid integer") from exc
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"{value!r} must be greater than 0")
    return ivalue


def non_negative_int(value: str) -> int:
    """Validate non-negative integer arguments (>= 0)."""
    try:
        ivalue = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a valid integer") from exc
    if ivalue < 0:
        raise argparse.ArgumentTypeError(f"{value!r} must be non-negative")
    return ivalue


# ── Version ──────────────────────────────────────────────


def build_version_text() -> str:
    from opscode._version import __version__

    return f"opscode {__version__}"


# ── CLI dependencies check ───────────────────────────────


def check_cli_dependencies() -> None:
    """Verify that required UI deps (textual, rich) are importable."""
    try:
        import rich  # noqa: F401
        import textual  # noqa: F401
    except ImportError as exc:
        sys.stderr.write(
            f"Missing required dependency: {exc}\n"
            "Install with: pip install opscode[ui]\n"
        )
        sys.exit(1)


# ── Stdin detection ──────────────────────────────────────


def _apply_stdin_pipe(args: argparse.Namespace) -> None:
    """Detect piped stdin and treat it as a non-interactive prompt."""
    if getattr(args, "non_interactive_message", None):
        return
    if getattr(args, "stdin", False) or not sys.stdin.isatty():
        try:
            piped = sys.stdin.read().strip()
        except Exception:
            return
        if piped:
            args.non_interactive_message = piped


# ── Approval Mode Resolution ─────────────────────────────


def _resolve_approval_mode(args: argparse.Namespace) -> ApprovalMode:
    """Resolve explicit flags into a typed ApprovalMode."""
    if getattr(args, "yolo", False):
        return ApprovalMode.YOLO
    if getattr(args, "auto_approve", False):
        return ApprovalMode.AUTO
    return ApprovalMode.MANUAL


# ── Bare Command Group Help ──────────────────────────────


def _show_bare_command_group_help(args: argparse.Namespace) -> bool:
    """Show dedicated help screen for a bare command group invocation."""
    from opscode import ui

    command = getattr(args, "command", None)
    if command == "agents" and getattr(args, "agents_command", None) is None:
        ui.show_agents_help()
        return True
    if command == "threads" and getattr(args, "threads_command", None) is None:
        ui.show_threads_help()
        return True
    if command == "skills" and getattr(args, "skills_command", None) is None:
        ui.show_skills_help()
        return True
    if command in {"plugin", "plugins"} and getattr(args, "plugin_command", None) is None:
        ui.show_plugins_help()
        return True
    if command == "mcp" and getattr(args, "mcp_command", None) is None:
        ui.show_mcp_help()
        return True
    if command == "tools" and getattr(args, "tools_command", None) is None:
        ui.show_tools_help()
        return True
    return False


# ── Argument parser ──────────────────────────────────────


def parse_args() -> argparse.Namespace:
    """Parse command line arguments matching standard CLI options schema."""
    from opscode.cli.commands.auth import setup_auth_parser
    from opscode.cli.commands.config import setup_config_parser
    from opscode.cli.commands.mcp import setup_mcp_parsers
    from opscode.plugins.commands_cli import setup_plugin_parser
    from opscode.skills.commands import setup_skills_parser

    def _make_help_action(help_fn: Callable[[], None]) -> type[argparse.Action]:
        class _ShowHelp(argparse.Action):
            def __init__(
                self,
                option_strings: list[str],
                dest: str = argparse.SUPPRESS,
                default: str = argparse.SUPPRESS,
                **kwargs: Any,
            ) -> None:
                super().__init__(
                    option_strings=option_strings,
                    dest=dest,
                    default=default,
                    nargs=0,
                    **kwargs,
                )

            def __call__(
                self,
                parser: argparse.ArgumentParser,
                namespace: argparse.Namespace,
                values: str | Sequence[Any] | None,
                option_string: str | None = None,
            ) -> None:
                with contextlib.suppress(BrokenPipeError):
                    help_fn()
                parser.exit()

        return _ShowHelp

    def _lazy_help(fn_name: str) -> Callable[[], None]:
        def _show() -> None:
            from opscode import ui

            getattr(ui, fn_name)()

        return _show

    def help_parent(help_fn: Callable[[], None]) -> list[argparse.ArgumentParser]:
        parent = argparse.ArgumentParser(add_help=False)
        parent.add_argument("-h", "--help", action=_make_help_action(help_fn))
        return [parent]

    parser = argparse.ArgumentParser(
        prog="opscode",
        description="OpsCode — AI Coding & DevOps Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Help command
    subparsers.add_parser(
        "help",
        help="Show help information",
        add_help=False,
        parents=help_parent(_lazy_help("show_help")),
    )

    # Agents subcommand
    agents_parser = subparsers.add_parser(
        "agents",
        help="Manage agents",
        add_help=False,
        parents=help_parent(_lazy_help("show_agents_help")),
    )
    add_json_output_arg(agents_parser)
    agents_sub = agents_parser.add_subparsers(dest="agents_command")

    agents_list = agents_sub.add_parser(
        "list",
        aliases=["ls"],
        help="List all agents",
        add_help=False,
        parents=help_parent(_lazy_help("show_list_help")),
    )
    add_json_output_arg(agents_list)

    agents_reset = agents_sub.add_parser(
        "reset",
        help="Reset an agent's prompt to default",
        add_help=False,
        parents=help_parent(_lazy_help("show_reset_help")),
    )
    add_json_output_arg(agents_reset)
    agents_reset.add_argument("--agent", required=True, help="Name of agent to reset")
    agents_reset.add_argument("--target", dest="source_agent", help="Copy prompt from another agent")
    agents_reset.add_argument("--dry-run", action="store_true", help="Show changes without applying")

    # Skills subcommand
    setup_skills_parser(
        subparsers,
        make_help_action=_make_help_action,
        add_output_args=add_json_output_arg,
    )

    # MCP subcommand
    setup_mcp_parsers(
        subparsers,
        make_help_action=_make_help_action,
    )

    # Plugin subcommand
    setup_plugin_parser(
        subparsers,
        make_help_action=_make_help_action,
        add_output_args=add_json_output_arg,
    )

    # Config subcommand
    setup_config_parser(
        subparsers,
        make_help_action=_make_help_action,
        add_output_args=add_json_output_arg,
    )

    # Auth subcommand
    setup_auth_parser(
        subparsers,
        make_help_action=_make_help_action,
    )

    # Threads subcommand
    threads_parser = subparsers.add_parser(
        "threads",
        help="Manage conversation threads",
        add_help=False,
        parents=help_parent(_lazy_help("show_threads_help")),
    )
    add_json_output_arg(threads_parser)
    threads_sub = threads_parser.add_subparsers(dest="threads_command")

    threads_list = threads_sub.add_parser(
        "list",
        aliases=["ls"],
        help="List threads",
        add_help=False,
        parents=help_parent(_lazy_help("show_threads_list_help")),
    )
    add_json_output_arg(threads_list)
    threads_list.add_argument("--agent", default=None, help="Filter by agent name")
    threads_list.add_argument("-n", "--limit", type=int, default=None, help="Max threads to display (default: 20)")
    threads_list.add_argument("--sort", choices=["created", "updated"], default=None, help="Sort timestamp")
    threads_list.add_argument("--branch", default=None, help="Filter by git branch")
    threads_list.add_argument("--cwd", default=None, help="Filter by working directory")
    threads_list.add_argument("-v", "--verbose", action="store_true", default=False, help="Show all columns")
    threads_list.add_argument("-r", "--relative", action=argparse.BooleanOptionalAction, default=None, help="Show relative timestamps")

    threads_delete = threads_sub.add_parser(
        "delete",
        help="Delete a thread",
        add_help=False,
        parents=help_parent(_lazy_help("show_threads_delete_help")),
    )
    add_json_output_arg(threads_delete)
    threads_delete.add_argument("thread_id", help="Thread ID to delete")
    threads_delete.add_argument("--dry-run", action="store_true", help="Show changes without applying")

    # Doctor subcommand
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Print install health and diagnostics",
        add_help=False,
        parents=help_parent(_lazy_help("show_doctor_help")),
    )
    add_json_output_arg(doctor_parser)

    # Tools subcommand
    tools_parser = subparsers.add_parser(
        "tools",
        help="Manage external tools",
        add_help=False,
        parents=help_parent(_lazy_help("show_tools_help")),
    )
    add_json_output_arg(tools_parser)
    tools_sub = tools_parser.add_subparsers(dest="tools_command")

    tools_install = tools_sub.add_parser(
        "install",
        help="Install or repair managed external tools (e.g. ripgrep)",
        add_help=False,
        parents=help_parent(_lazy_help("show_tools_install_help")),
    )
    add_json_output_arg(tools_install)

    tools_list = tools_sub.add_parser(
        "list",
        help="List tools available to the agent",
        add_help=False,
        parents=help_parent(_lazy_help("show_tools_list_help")),
    )
    add_json_output_arg(tools_list)

    # === Top-Level Flags & Defaults ===

    # Resume thread
    parser.add_argument(
        "-r",
        "--resume",
        dest="resume_thread",
        nargs="?",
        const="__MOST_RECENT__",
        default=None,
        metavar="ID",
        help="Resume thread: -r for most recent, -r <ID> for specific thread",
    )

    # Agent identity
    parser.add_argument(
        "-a",
        "--agent",
        default=None,
        metavar="NAME",
        help="Agent to use (default: opscode)",
    )

    # Model & Parameters
    parser.add_argument(
        "-M",
        "--model",
        metavar="MODEL",
        help="Model to use (e.g., anthropic:claude-opus-4-8, gpt-5.5). Provider is auto-detected from model name.",
    )
    parser.add_argument(
        "--model-params",
        metavar="JSON",
        help="Extra kwargs to pass to model as JSON string",
    )
    parser.add_argument(
        "--max-retries",
        type=non_negative_int,
        default=None,
        metavar="N",
        help="Override max retries for transient model errors",
    )
    parser.add_argument(
        "--profile-override",
        metavar="JSON",
        help="Override model profile fields as JSON string",
    )
    parser.add_argument(
        "--default-model",
        metavar="MODEL",
        nargs="?",
        const="__SHOW__",
        default=None,
        help="Set or show the default model for future launches",
    )
    parser.add_argument(
        "--clear-default-model",
        action="store_true",
        help="Clear configured default model",
    )

    # Initial prompts & Startup commands
    parser.add_argument(
        "-m",
        "--message",
        "--initial-prompt",
        dest="initial_prompt",
        metavar="TEXT",
        help="Initial prompt to auto-submit when session starts",
    )
    parser.add_argument(
        "-s",
        "--skill",
        dest="initial_skill",
        metavar="NAME",
        help="Invoke a skill when session starts",
    )
    parser.add_argument(
        "--startup-cmd",
        dest="startup_cmd",
        metavar="CMD",
        help="Shell command executed at startup before first prompt",
    )

    # Non-interactive Mode & Limits
    parser.add_argument(
        "-n",
        "--non-interactive",
        dest="non_interactive_message",
        metavar="TEXT",
        help="Run a single task non-interactively and exit",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="Clean output for piping stdout (requires -n or piped stdin)",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        default=False,
        help="Buffer full response before writing (requires -n or piped stdin)",
    )
    parser.add_argument(
        "--max-turns",
        type=positive_int,
        default=None,
        metavar="N",
        help="Maximum agentic turns before stopping",
    )
    parser.add_argument(
        "--timeout",
        type=positive_int,
        default=None,
        metavar="SECONDS",
        help="Hard wall-clock timeout in seconds",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read input from stdin explicitly",
    )

    # Goal & Rubric
    parser.add_argument(
        "--goal",
        metavar="TEXT",
        help="Goal objective to turn into acceptance criteria in interactive mode",
    )
    parser.add_argument(
        "--rubric",
        metavar="TEXT|@PATH",
        help="Acceptance criteria text or '@path' for self-evaluation loop",
    )
    parser.add_argument(
        "--rubric-model",
        metavar="MODEL",
        help="Grader model for rubric self-evaluation",
    )
    parser.add_argument(
        "--rubric-max-iterations",
        type=positive_int,
        default=None,
        metavar="N",
        help="Max grader iterations per rubric attempt",
    )
    parser.add_argument(
        "--recursion-limit",
        type=positive_int,
        default=None,
        metavar="N",
        help="Override main agent's recursion_limit (default: 2000)",
    )

    # Approval Modes
    approval_group = parser.add_mutually_exclusive_group()
    approval_group.add_argument(
        "-y",
        "--auto-approve",
        action="store_true",
        default=False,
        help="Interactive TUI mode: enable classifier-backed Auto mode.",
    )
    approval_group.add_argument(
        "--yolo",
        action="store_true",
        default=False,
        help="Interactive mode: run gated actions without review after acknowledgement.",
    )

    # Sandbox & Shell
    parser.add_argument(
        "-S",
        "--shell-allow-list",
        metavar="LIST",
        help="Comma-separated list of allowed shell commands ('recommended', 'all', or list)",
    )
    parser.add_argument(
        "--sandbox",
        nargs="?",
        const="__DEFAULT__",
        default="none",
        metavar="TYPE",
        help="Remote sandbox for code execution (default: none)",
    )
    parser.add_argument(
        "--sandbox-id",
        metavar="ID",
        help="Existing remote sandbox ID to attach to",
    )
    parser.add_argument(
        "--sandbox-snapshot-name",
        metavar="NAME",
        help="Snapshot or blueprint name to create or attach",
    )
    parser.add_argument(
        "--sandbox-setup",
        metavar="PATH",
        help="Path to setup shell script to run after sandbox creation",
    )

    # Interpreter & Filesystem Tools
    parser.add_argument(
        "--interpreter",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Toggle JS interpreter (`js_eval`) middleware",
    )
    parser.add_argument(
        "--interpreter-tools",
        metavar="VALUE",
        help="PTC allowlist for `js_eval`: 'safe', 'all', or comma-separated list",
    )
    parser.add_argument(
        "--allow-fs-tools",
        metavar="LIST",
        default="all",
        help="Allowlist of filesystem tools ('all' or comma-separated list)",
    )

    # MCP & Security
    parser.add_argument(
        "--mcp-config",
        metavar="PATH",
        help="Path to explicit MCP JSON configuration file",
    )
    parser.add_argument(
        "--no-mcp",
        action="store_true",
        default=False,
        help="Disable all MCP tool loading",
    )
    parser.add_argument(
        "--trust-project-mcp",
        action="store_true",
        default=False,
        help="Skip interactive approval prompt for project-level MCP configs",
    )
    parser.add_argument(
        "--trust-project-hooks",
        action="store_true",
        default=False,
        help="Trust project-level `.opscode/hooks.json` command handlers",
    )
    parser.add_argument(
        "--acp",
        action="store_true",
        default=False,
        help="Run as an ACP server over stdio instead of launching Textual UI",
    )
    # Meta
    add_json_output_arg(parser, default="text")
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=build_version_text(),
    )
    parser.add_argument(
        "-h",
        "--help",
        action=_make_help_action(_lazy_help("show_help")),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose logging",
    )

    known_subcommands = {
        "help",
        "agents",
        "skills",
        "mcp",
        "plugin",
        "plugins",
        "config",
        "auth",
        "threads",
        "doctor",
        "tools",
    }

    raw_args = list(sys.argv[1:])

    flags_with_values: set[str] = set()
    optional_val_flags: set[str] = set()
    for act in parser._actions:
        if act.nargs == 0:
            continue
        if act.nargs == "?":
            for opt in act.option_strings:
                optional_val_flags.add(opt)
        else:
            for opt in act.option_strings:
                flags_with_values.add(opt)

    # Check if first positional argument is a known subcommand
    is_subcommand = False
    k = 0
    while k < len(raw_args):
        a = raw_args[k]
        if a in flags_with_values:
            k += 2
            continue
        if a in optional_val_flags:
            if k + 1 < len(raw_args) and not raw_args[k + 1].startswith("-") and raw_args[k + 1] not in known_subcommands:
                k += 2
                continue
            k += 1
            continue
        if not a.startswith("-"):
            if a in known_subcommands:
                is_subcommand = True
            break
        k += 1

    if is_subcommand:
        parsed = parser.parse_args(raw_args)
        parsed.prompt = getattr(parsed, "non_interactive_message", None)
        return parsed

    processed_args: list[str] = []
    i = 0
    while i < len(raw_args):
        arg = raw_args[i]
        if arg in flags_with_values:
            processed_args.append(arg)
            if i + 1 < len(raw_args):
                processed_args.append(raw_args[i + 1])
                i += 2
                continue
            i += 1
            continue
        elif arg in optional_val_flags:
            processed_args.append(arg)
            if (
                i + 1 < len(raw_args)
                and not raw_args[i + 1].startswith("-")
                and raw_args[i + 1] not in known_subcommands
            ):
                processed_args.append(raw_args[i + 1])
                i += 2
                continue
            i += 1
            continue
        elif (
            not arg.startswith("-")
            and arg not in known_subcommands
            and not any(a in {"-n", "--non-interactive"} for a in processed_args)
        ):
            processed_args.extend(["-n", arg])
            i += 1
            continue
        processed_args.append(arg)
        i += 1

    parsed = parser.parse_args(processed_args)
    if getattr(parsed, "non_interactive_message", None):
        parsed.prompt = parsed.non_interactive_message
    else:
        parsed.prompt = None
    return parsed


# ── Validation ───────────────────────────────────────────


def _validate_args(args: argparse.Namespace) -> None:
    """Validate mutual exclusions and required combinations."""
    from rich.console import Console as _Console

    stderr = _Console(stderr=True)

    # --quiet / --no-stream require -n
    if (getattr(args, "quiet", False) or getattr(args, "no_stream", False)) and not getattr(args, "non_interactive_message", None):
        flags = []
        if getattr(args, "quiet", False):
            flags.append("--quiet")
        if getattr(args, "no_stream", False):
            flags.append("--no-stream")
        flag = " and ".join(flags)
        stderr.print(
            f"[bold red]Error:[/bold red] {flag} requires "
            "--non-interactive (-n) or piped stdin\n"
            "  opscode -n 'summarize README.md' --quiet"
        )
        sys.exit(2)

    # --max-turns requires -n
    if getattr(args, "max_turns", None) is not None and not getattr(args, "non_interactive_message", None):
        stderr.print(
            "[bold red]Error:[/bold red] --max-turns requires "
            "--non-interactive (-n) or piped stdin\n"
            "  opscode -n 'refactor auth module' --max-turns 5"
        )
        sys.exit(2)

    # --timeout requires -n
    if getattr(args, "timeout", None) is not None and not getattr(args, "non_interactive_message", None):
        stderr.print(
            "[bold red]Error:[/bold red] --timeout requires "
            "--non-interactive (-n) or piped stdin\n"
            "  opscode -n 'run the test suite' --timeout 120"
        )
        sys.exit(2)

    # --rubric requires -n
    rubric_set = any(
        getattr(args, attr, None) is not None
        for attr in ("rubric", "rubric_model", "rubric_max_iterations")
    )
    if rubric_set and not getattr(args, "non_interactive_message", None):
        stderr.print(
            "[bold red]Error:[/bold red] --rubric/--rubric-model/"
            "--rubric-max-iterations require "
            "--non-interactive (-n) or piped stdin\n"
            "  opscode -n 'implement X' --rubric 'tests pass'"
        )
        sys.exit(2)

    # --goal is interactive-only
    if getattr(args, "goal", None) is not None and getattr(args, "non_interactive_message", None):
        stderr.print(
            "[bold red]Error:[/bold red] --goal is only supported in "
            "interactive mode.\n"
            "  opscode --goal 'add OAuth refresh handling'"
        )
        sys.exit(2)

    # --no-mcp and --mcp-config are mutually exclusive
    if getattr(args, "no_mcp", False) and getattr(args, "mcp_config", None):
        stderr.print(
            "[bold red]Error:[/bold red] --no-mcp and --mcp-config "
            "are mutually exclusive.\n"
            "  opscode --mcp-config path/to/config.json\n"
            "  opscode --no-mcp"
        )
        sys.exit(2)


def _run_async_coro(coro: Any) -> Any:
    """Run an async coroutine safely, even inside an already-running event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ── Main Entrypoint ──────────────────────────────────────


def cli_main() -> None:
    """Main CLI entry point for the ``opscode`` console script."""
    # Fast path for --version
    if len(sys.argv) == 2 and sys.argv[1] in {"-v", "--version"}:
        print(build_version_text())
        sys.exit(0)

    # macOS gRPC optimization
    if sys.platform == "darwin":
        os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"

    check_cli_dependencies()

    try:
        args = parse_args()

        # Fast path for bare command group help
        if _show_bare_command_group_help(args):
            return

        # Handle Subcommands
        command = getattr(args, "command", None)
        raw_fmt = getattr(args, "output_format", "text")
        output_format: OutputFormat = "json" if raw_fmt == "json" else "text"

        if command == "help":
            from opscode.ui.ui_help import show_help

            show_help()
            sys.exit(0)

        if command == "config":
            from opscode.cli.commands.config import run_config_command

            sys.exit(run_config_command(args))

        if command == "auth":
            from opscode.cli.commands.auth import run_auth_command

            sys.exit(run_auth_command(args))

        if command == "doctor":
            from opscode.cli.commands.doctor import run_doctor_command

            sys.exit(run_doctor_command(args))

        if command == "tools":
            from opscode.cli.commands.tools import run_tools_command

            sys.exit(run_tools_command(args))

        if command in {"plugin", "plugins"}:
            from opscode.plugins.commands_cli import execute_plugin_command

            sys.exit(execute_plugin_command(args))

        if command == "skills":
            from opscode.skills.commands import execute_skills_command

            sys.exit(execute_skills_command(args))

        if command == "threads":
            from opscode.cli.commands.threads import delete_thread_command, list_threads_command

            subcmd = getattr(args, "threads_command", None)
            if subcmd in {"list", "ls"}:
                _run_async_coro(
                    list_threads_command(
                        agent_name=getattr(args, "agent", None),
                        limit=getattr(args, "limit", None),
                        sort_by=getattr(args, "sort", None),
                        branch=getattr(args, "branch", None),
                        cwd=getattr(args, "cwd", None),
                        verbose=getattr(args, "verbose", False),
                        relative=getattr(args, "relative", None),
                        output_format=output_format,
                    )
                )
                sys.exit(0)
            elif subcmd == "delete":
                _run_async_coro(
                    delete_thread_command(
                        args.thread_id,
                        dry_run=getattr(args, "dry_run", False),
                        output_format=output_format,
                    )
                )
                sys.exit(0)

        if command == "agents":
            from opscode.cli.commands.agents import list_agents, reset_agent

            subcmd = getattr(args, "agents_command", None)
            if subcmd in {"list", "ls"}:
                list_agents(output_format=output_format)
                sys.exit(0)
            elif subcmd == "reset":
                reset_agent(
                    args.agent,
                    getattr(args, "source_agent", None),
                    dry_run=getattr(args, "dry_run", False),
                    output_format=output_format,
                )
                sys.exit(0)

        if command == "mcp":
            from opscode.cli.commands.mcp import run_mcp_config, run_mcp_list, run_mcp_login

            subcmd = getattr(args, "mcp_command", None)
            if subcmd == "config":
                sys.exit(run_mcp_config(output_format=output_format))
            elif subcmd in {"list", "ls"}:
                sys.exit(run_mcp_list(output_format=output_format))
            elif subcmd == "login":
                config_path = getattr(args, "config_path", None) or getattr(args, "mcp_config", None)
                sys.exit(_run_async_coro(run_mcp_login(server=args.server, config_path=config_path)))

        # ── Handle --default-model / --clear-default-model ──
        if getattr(args, "clear_default_model", False):
            from opscode.model.config import clear_default_model

            if clear_default_model():
                print("Default model cleared.")
            else:
                sys.stderr.write("Error: Could not clear default model.\n")
                sys.exit(1)
            sys.exit(0)

        if getattr(args, "default_model", None) is not None:
            from opscode.model.config import load_default_model, save_default_model
            from opscode.model.factory import normalize_model_spec

            if args.default_model == "__SHOW__":
                current_default = load_default_model()
                if current_default:
                    print(f"Default model: {current_default}")
                else:
                    print("No default model set.")
                sys.exit(0)

            normalized = normalize_model_spec(args.default_model)
            if save_default_model(normalized):
                print(f"Default model set to {normalized}")
            else:
                sys.stderr.write("Error: Could not save default model.\n")
                sys.exit(1)
            sys.exit(0)

        # Merge positional prompt into non_interactive_message
        if getattr(args, "prompt", None) and not getattr(args, "non_interactive_message", None):
            args.non_interactive_message = args.prompt

        _apply_stdin_pipe(args)

        # Parse model params JSON
        model_params: dict[str, Any] | None = None
        raw_kwargs = getattr(args, "model_params", None)
        if raw_kwargs:
            try:
                model_params = json.loads(raw_kwargs)
            except json.JSONDecodeError as e:
                sys.stderr.write(f"Error: --model-params is not valid JSON: {e}\n")
                sys.exit(1)
            if not isinstance(model_params, dict):
                sys.stderr.write("Error: --model-params must be a JSON object\n")
                sys.exit(1)

        # Parse profile override JSON
        profile_override: dict[str, Any] | None = None
        raw_profile = getattr(args, "profile_override", None)
        if raw_profile:
            try:
                profile_override = json.loads(raw_profile)
            except json.JSONDecodeError as e:
                sys.stderr.write(f"Error: --profile-override is not valid JSON: {e}\n")
                sys.exit(1)
            if not isinstance(profile_override, dict):
                sys.stderr.write("Error: --profile-override must be a JSON object\n")
                sys.exit(1)

        _validate_args(args)

        from opscode.config.settings import _ensure_bootstrap

        _ensure_bootstrap()

        # Configure verbose logging
        if getattr(args, "verbose", False):
            os.environ["OPSCODE_DEBUG"] = "1"
            from opscode._debug import configure_debug_logging

            configure_debug_logging(logging.getLogger("opscode"))

        # Resolve model specifier
        from opscode.model.factory import normalize_model_spec

        raw_model = getattr(args, "model", None)
        model_spec = normalize_model_spec(raw_model) if isinstance(raw_model, str) and raw_model else None

        # Resolve agent identity & approval mode
        assistant_id = getattr(args, "agent", None) or "opscode"
        approval_mode = _resolve_approval_mode(args)

        # Parse shell allow list
        shell_allow_list: list[str] | None = None
        if getattr(args, "shell_allow_list", None):
            from opscode.config.settings import parse_shell_allow_list

            shell_allow_list = parse_shell_allow_list(args.shell_allow_list)

        # ── Route: non-interactive mode ──
        if getattr(args, "non_interactive_message", None):
            from opscode.cli.non_interactive import run_non_interactive

            timeout = getattr(args, "timeout", None)
            exit_code = asyncio.run(
                run_non_interactive(
                    prompt=args.non_interactive_message,
                    model=model_spec,
                    model_params=model_params,
                    profile_override=profile_override,
                    assistant_id=assistant_id,
                    auto_approve=approval_mode != ApprovalMode.MANUAL,
                    shell_allow_list=shell_allow_list,
                    quiet=getattr(args, "quiet", False),
                    no_stream=getattr(args, "no_stream", False),
                    max_turns=getattr(args, "max_turns", None),
                    timeout=float(timeout) if timeout is not None else None,
                    rubric=getattr(args, "rubric", None),
                    rubric_model=getattr(args, "rubric_model", None),
                    rubric_max_iterations=getattr(args, "rubric_max_iterations", None),
                    recursion_limit=getattr(args, "recursion_limit", None),
                    initial_skill=getattr(args, "initial_skill", None),
                    startup_cmd=getattr(args, "startup_cmd", None),
                    mcp_config_path=getattr(args, "mcp_config", None),
                    no_mcp=getattr(args, "no_mcp", False),
                    trust_project_mcp=getattr(args, "trust_project_mcp", False),
                    enable_interpreter=getattr(args, "interpreter", None),
                    interpreter_ptc=getattr(args, "interpreter_tools", None),
                    allow_fs_tools=getattr(args, "allow_fs_tools", "all"),
                )
            )
            sys.exit(exit_code)

        # ── Route: interactive TUI mode ──
        from opscode.cli.interactive import run_interactive

        exit_code = run_interactive(
            model=model_spec,
            model_params=model_params,
            profile_override=profile_override,
            assistant_id=assistant_id,
            auto_approve=approval_mode != ApprovalMode.MANUAL,
            resume_thread=getattr(args, "resume_thread", None),
            goal=getattr(args, "goal", None),
            initial_prompt=getattr(args, "initial_prompt", None),
            initial_skill=getattr(args, "initial_skill", None),
            startup_cmd=getattr(args, "startup_cmd", None),
            shell_allow_list=shell_allow_list,
            mcp_config_path=getattr(args, "mcp_config", None),
            no_mcp=getattr(args, "no_mcp", False),
            trust_project_mcp=getattr(args, "trust_project_mcp", False),
            enable_interpreter=getattr(args, "interpreter", None),
            interpreter_ptc=getattr(args, "interpreter_tools", None),
            allow_fs_tools=getattr(args, "allow_fs_tools", "all"),
            recursion_limit=getattr(args, "recursion_limit", None),
        )
        sys.exit(exit_code)

    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        logger.exception("Fatal error in opscode CLI")
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
