"""DCoder CLI entry point and argument parser.

Routes between interactive TUI mode (default) and non-interactive headless
mode (``-n`` / positional prompt / piped stdin).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any

from dcoder.approval_mode import ApprovalMode, coerce_approval_mode

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
    from dcoder._version import __version__

    return f"dcoder {__version__}"


# ── CLI dependencies check ───────────────────────────────


def check_cli_dependencies() -> None:
    """Verify that required UI deps (textual, rich) are importable."""
    try:
        import rich  # noqa: F401
        import textual  # noqa: F401
    except ImportError as exc:
        sys.stderr.write(
            f"Missing required dependency: {exc}\n"
            "Install with: pip install dcoder[ui]\n"
        )
        sys.exit(1)


# ── Stdin detection ──────────────────────────────────────


def _apply_stdin_pipe(args: argparse.Namespace) -> None:
    """Detect piped stdin and treat it as a non-interactive prompt."""
    if args.non_interactive_message:
        return
    if not sys.stdin.isatty():
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
    if getattr(args, "auto_approve", None) is True:
        return ApprovalMode.AUTO
    return ApprovalMode.MANUAL


# ── Argument parser ──────────────────────────────────────


def parse_args() -> argparse.Namespace:
    """Parse command line arguments matching standard CLI options schema.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="dcoder",
        description="DCoder — DevOps Coding Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # === Positionals & Prompts ===
    parser.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Non-interactive prompt (alternative to -n)",
    )

    # === Thread management ===
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

    # === Agent ===
    parser.add_argument(
        "-a",
        "--agent",
        default=None,
        metavar="NAME",
        help="Agent to use (default: dcoder)",
    )

    # === Model & Execution Profile ===
    parser.add_argument(
        "-M",
        "--model",
        dest="model",
        metavar="MODEL",
        help="Model specifier (e.g. claude-opus-4-7, gpt-5.5)",
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
        help="Set or show current default model for future launches",
    )
    parser.add_argument(
        "--clear-default-model",
        action="store_true",
        help="Clear configured default model",
    )

    # === Startup Prompts & Commands ===
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
        help="Invoke a skill when interactive session starts",
    )
    parser.add_argument(
        "--startup-cmd",
        dest="startup_cmd",
        metavar="CMD",
        help="Shell command executed at startup before first prompt",
    )

    # === Non-interactive Mode & Limits ===
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

    # === Goal & Rubric Evaluation ===
    parser.add_argument(
        "--goal",
        metavar="TEXT",
        help="Goal objective to generate acceptance criteria in interactive mode",
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
        help="Override main agent's recursion_limit (defaults to 2000)",
    )

    # === Approval Modes ===
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

    # === Shell & Sandbox ===
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

    # === Interpreter & Tools ===
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

    # === MCP & Security ===
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
        help="Trust project-level `.dcoder/hooks.json` command handlers",
    )
    parser.add_argument(
        "--acp",
        action="store_true",
        default=False,
        help="Run as an ACP server over stdio instead of launching Textual UI",
    )

    # === Meta ===
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=build_version_text(),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose logging",
    )

    return parser.parse_args()


# ── Validation ───────────────────────────────────────────


def _validate_args(args: argparse.Namespace) -> None:
    """Validate mutual exclusions and required combinations."""
    from rich.console import Console as _Console

    stderr = _Console(stderr=True)

    # --quiet / --no-stream require -n
    if (args.quiet or args.no_stream) and not args.non_interactive_message:
        flags = []
        if args.quiet:
            flags.append("--quiet")
        if args.no_stream:
            flags.append("--no-stream")
        flag = " and ".join(flags)
        stderr.print(
            f"[bold red]Error:[/bold red] {flag} requires "
            "--non-interactive (-n) or piped stdin\n"
            "  dcoder -n 'summarize README.md' --quiet"
        )
        sys.exit(2)

    # --max-turns requires -n
    if args.max_turns is not None and not args.non_interactive_message:
        stderr.print(
            "[bold red]Error:[/bold red] --max-turns requires "
            "--non-interactive (-n) or piped stdin\n"
            "  dcoder -n 'refactor auth module' --max-turns 5"
        )
        sys.exit(2)

    # --timeout requires -n
    if args.timeout is not None and not args.non_interactive_message:
        stderr.print(
            "[bold red]Error:[/bold red] --timeout requires "
            "--non-interactive (-n) or piped stdin\n"
            "  dcoder -n 'run the test suite' --timeout 120"
        )
        sys.exit(2)

    # --rubric requires -n
    rubric_set = any(
        getattr(args, attr, None) is not None
        for attr in ("rubric", "rubric_model", "rubric_max_iterations")
    )
    if rubric_set and not args.non_interactive_message:
        stderr.print(
            "[bold red]Error:[/bold red] --rubric/--rubric-model/"
            "--rubric-max-iterations require "
            "--non-interactive (-n) or piped stdin\n"
            "  dcoder -n 'implement X' --rubric 'tests pass'"
        )
        sys.exit(2)

    # --goal is interactive-only
    if args.goal is not None and args.non_interactive_message:
        stderr.print(
            "[bold red]Error:[/bold red] --goal is only supported in "
            "interactive mode.\n"
            "  dcoder --goal 'add OAuth refresh handling'"
        )
        sys.exit(2)

    # --no-mcp and --mcp-config are mutually exclusive
    if args.no_mcp and args.mcp_config:
        stderr.print(
            "[bold red]Error:[/bold red] --no-mcp and --mcp-config "
            "are mutually exclusive.\n"
            "  dcoder --mcp-config path/to/config.json\n"
            "  dcoder --no-mcp"
        )
        sys.exit(2)


# ── Main entry point ─────────────────────────────────────


def cli_main() -> None:
    """Main CLI entry point for the ``dcoder`` console script."""
    if len(sys.argv) == 2 and sys.argv[1] in {"-v", "--version"}:  # noqa: PLR2004
        print(build_version_text())  # noqa: T201
        sys.exit(0)

    check_cli_dependencies()

    try:
        args = parse_args()

        # Merge positional prompt into non_interactive_message
        if args.prompt and not args.non_interactive_message:
            args.non_interactive_message = args.prompt

        _apply_stdin_pipe(args)

        # Parse model params JSON
        model_params: dict[str, Any] | None = None
        raw_kwargs = args.model_params
        if raw_kwargs:
            import json

            try:
                model_params = json.loads(raw_kwargs)
            except json.JSONDecodeError as e:
                sys.stderr.write(f"Error: --model-params is not valid JSON: {e}\n")
                sys.exit(1)
            if not isinstance(model_params, dict):
                sys.stderr.write("Error: --model-params must be a JSON object\n")
                sys.exit(1)

        _validate_args(args)

        from dcoder.config.settings import _ensure_bootstrap
        _ensure_bootstrap()

        # Configure verbose logging
        if args.verbose:
            os.environ["DCODER_CODE_DEBUG"] = "1"
            from dcoder._debug import configure_debug_logging
            configure_debug_logging(logging.getLogger("dcoder"))

        # Resolve agent identity & approval mode
        assistant_id = args.agent or "dcoder"
        approval_mode = _resolve_approval_mode(args)

        # Parse shell allow list
        shell_allow_list: list[str] | None = None
        if args.shell_allow_list:
            from dcoder.config.settings import parse_shell_allow_list

            shell_allow_list = parse_shell_allow_list(args.shell_allow_list)

        # ── Route: non-interactive mode ──
        if args.non_interactive_message:
            from dcoder.cli.non_interactive import run_non_interactive

            exit_code = asyncio.run(
                run_non_interactive(
                    prompt=args.non_interactive_message,
                    model=args.model,
                    model_params=model_params,
                    assistant_id=assistant_id,
                    auto_approve=approval_mode != ApprovalMode.MANUAL,
                    shell_allow_list=shell_allow_list,
                    quiet=args.quiet,
                    no_stream=args.no_stream,
                    max_turns=args.max_turns,
                    timeout=args.timeout,
                    rubric=args.rubric,
                    rubric_model=args.rubric_model,
                    rubric_max_iterations=args.rubric_max_iterations,
                    mcp_config_path=args.mcp_config,
                    no_mcp=args.no_mcp,
                    trust_project_mcp=args.trust_project_mcp,
                )
            )
            sys.exit(exit_code)

        # ── Route: interactive TUI mode ──
        from dcoder.cli.interactive import run_interactive

        exit_code = run_interactive(
            model=args.model,
            model_params=model_params,
            assistant_id=assistant_id,
            auto_approve=approval_mode != ApprovalMode.MANUAL,
            resume_thread=args.resume_thread,
            goal=args.goal,
            shell_allow_list=shell_allow_list,
            mcp_config_path=args.mcp_config,
            no_mcp=args.no_mcp,
            trust_project_mcp=args.trust_project_mcp,
        )
        sys.exit(exit_code)

    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        logger.exception("Fatal error in dcoder CLI")
        sys.exit(1)
