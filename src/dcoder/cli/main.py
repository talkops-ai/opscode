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

logger = logging.getLogger(__name__)


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


# ── Argument parser ──────────────────────────────────────


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="dcoder",
        description="DCoder — DevOps Coding Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # === Mode selection ===
    parser.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Non-interactive prompt (alternative to -n)",
    )
    parser.add_argument(
        "-n",
        "--non-interactive",
        dest="non_interactive_message",
        metavar="MSG",
        default=None,
        help="Run in non-interactive mode with the given prompt",
    )

    # === Model ===
    parser.add_argument("-m", "--model", default=None, help="LLM model (provider:name)")
    parser.add_argument(
        "--model-params", default=None, help="JSON string of model parameters"
    )

    # === Agent ===
    parser.add_argument(
        "-a",
        "--agent",
        default=None,
        help="Agent identity (default: dcoder)",
    )

    # === Shell & Approval ===
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        default=False,
        help="Approve all tool calls automatically",
    )
    parser.add_argument(
        "--shell-allow-list",
        default=None,
        help="Comma-separated allowed shell commands (or 'all'/'recommended')",
    )

    # === Thread management ===
    parser.add_argument(
        "-r",
        "--resume",
        dest="resume_thread",
        default=None,
        help="Resume a specific thread by ID",
    )

    # === Non-interactive options ===
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress diagnostics (non-interactive only)",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        default=False,
        help="Buffer full response (non-interactive only)",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="Maximum agent turns (non-interactive only)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Timeout in seconds (non-interactive only)",
    )

    # === Rubric (non-interactive) ===
    parser.add_argument("--rubric", default=None, help="Acceptance criteria text")
    parser.add_argument("--rubric-model", default=None, help="Model for rubric grading")
    parser.add_argument(
        "--rubric-max-iterations",
        type=int,
        default=None,
        help="Max rubric grading iterations",
    )

    # === Goal (interactive) ===
    parser.add_argument(
        "--goal", default=None, help="Set goal with acceptance criteria"
    )

    # === MCP ===
    parser.add_argument(
        "--no-mcp",
        action="store_true",
        default=False,
        help="Disable all MCP servers",
    )
    parser.add_argument(
        "--mcp-config", default=None, help="Path to MCP config file"
    )
    parser.add_argument(
        "--trust-project-mcp",
        action="store_true",
        default=False,
        help="Auto-trust project-level MCP servers",
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
    # Fast path: print version without loading heavy deps
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

        # Resolve agent identity
        assistant_id = args.agent or "dcoder"

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
                    auto_approve=args.auto_approve,
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
            auto_approve=args.auto_approve,
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
