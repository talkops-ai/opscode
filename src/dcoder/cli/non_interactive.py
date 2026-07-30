"""Non-interactive (headless) runner for dcoder.

Connects to a LangGraph dev server subprocess via ``server_session``,
streams agent output to stdout, handles HITL interrupts via shell-allow-list
or auto-approve, and exits with an appropriate code.

Designed for CI/CD pipelines and scripted usage::

    dcoder -n "plan terraform for staging" --auto-approve
    dcoder -n "run test suite" --shell-allow-list recommended --quiet
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.text import Text

logger = logging.getLogger(__name__)

_MAX_HITL_ITERATIONS = 50
"""Safety cap on HITL interrupt round-trips to prevent infinite loops."""


# ── Stream state ─────────────────────────────────────────


@dataclass
class StreamState:
    """Mutable state accumulated while iterating over the agent stream."""

    quiet: bool = False
    """Suppress tool-call diagnostics; only agent text goes to stdout."""

    stream: bool = True
    """Stream text as it arrives (vs. buffer for --no-stream)."""

    full_response: list[str] = field(default_factory=list)
    """Accumulated text fragments from the AI message stream."""

    interrupt_occurred: bool = False
    """Whether any HITL interrupt was received during this pass."""

    input_tokens: int = 0
    output_tokens: int = 0


# ── Output helpers ───────────────────────────────────────


def _write_text(text: str) -> None:
    """Write agent response text to stdout."""
    sys.stdout.write(text)
    sys.stdout.flush()


def _write_newline() -> None:
    sys.stdout.write("\n")
    sys.stdout.flush()


def _notify_tool_call(
    console: Console,
    tool_name: str,
    args: dict[str, Any],
    *,
    quiet: bool,
) -> None:
    """Print a tool-call notification to stderr (unless quiet)."""
    if quiet:
        return
    desc = f"  ⚡ {tool_name}"
    if "command" in args:
        desc += f": {args['command']}"
    elif "path" in args:
        desc += f": {args['path']}"
    console.print(Text(desc, style="dim"))


# ── Shell allow-list gating ──────────────────────────────


def _should_auto_approve(
    tool_name: str,
    args: dict[str, Any],
    *,
    auto_approve: bool,
    shell_allow_list: list[str] | None,
) -> bool:
    """Decide whether to auto-approve a tool call.

    Returns ``True`` if the call should be approved, ``False`` if rejected.
    """
    if auto_approve:
        return True

    if shell_allow_list is None:
        return False

    # Non-shell tools: always approve when shell_allow_list is set
    if tool_name != "execute":
        return True

    command = args.get("command", "")
    for allowed in shell_allow_list:
        if allowed == "all":
            return True
        if command.startswith(allowed):
            return True

    return False


# ── Main runner ──────────────────────────────────────────


async def run_non_interactive(
    prompt: str,
    *,
    model: str | None = None,
    model_params: dict[str, Any] | None = None,
    assistant_id: str = "dcoder",
    auto_approve: bool = False,
    shell_allow_list: list[str] | None = None,
    quiet: bool = False,
    no_stream: bool = False,
    max_turns: int | None = None,
    timeout: float | None = None,
    rubric: str | None = None,
    rubric_model: str | None = None,
    rubric_max_iterations: int | None = None,
    mcp_config_path: str | None = None,
    no_mcp: bool = False,
    trust_project_mcp: bool = False,
) -> int:
    """Run a single task via LangGraph dev server, stream to stdout, exit.

    Args:
        prompt: The user's task prompt.
        model: Model identifier (e.g. ``"anthropic:claude-sonnet-4"``).
        model_params: Extra model parameters.
        assistant_id: Agent identity.
        auto_approve: Approve all tool calls automatically.
        shell_allow_list: Allowed shell commands list.
        quiet: Suppress diagnostics.
        no_stream: Buffer full response.
        max_turns: Maximum agent turns safety cap.
        timeout: Timeout in seconds safety cap.
        rubric: Acceptance criteria text.
        rubric_model: Model for rubric grading.
        rubric_max_iterations: Max rubric grading iterations.
        mcp_config_path: Path to MCP config file.
        no_mcp: Disable all MCP servers.
        trust_project_mcp: Auto-trust project MCP servers.

    Returns:
        Exit code: 0 for success, 1 for error.
    """
    from dcoder.cli.server_manager import server_session

    # Console writes to stderr so stdout is clean for agent output
    console = Console(stderr=True) if quiet else Console(stderr=True)

    state = StreamState(quiet=quiet, stream=not no_stream)
    start_time = time.monotonic()

    try:
        async with server_session(
            assistant_id=assistant_id,
            model_name=model,
            model_params=model_params,
            auto_approve=auto_approve,
            shell_allow_list=shell_allow_list,
            mcp_config_path=mcp_config_path,
            no_mcp=no_mcp,
            trust_project_mcp=trust_project_mcp,
            interactive=False,
        ) as (client, server):
            turn_count = 0
            hitl_iterations = 0
            thread_id = None  # Will be assigned by first run

            # Create a new thread
            thread = await client.threads.create()
            thread_id = thread["thread_id"]

            # Initial agent invocation
            input_msg = {"messages": [{"role": "user", "content": prompt}]}

            while True:
                # Safety caps
                if max_turns is not None and turn_count >= max_turns:
                    if not quiet:
                        console.print(
                            f"[yellow]Reached max-turns limit ({max_turns})[/yellow]"
                        )
                    break

                if timeout is not None:
                    elapsed = time.monotonic() - start_time
                    if elapsed >= timeout:
                        if not quiet:
                            console.print(
                                f"[yellow]Reached timeout ({timeout}s)[/yellow]"
                            )
                        break

                # Stream the agent turn
                state.interrupt_occurred = False
                async for chunk in client.runs.stream(
                    thread_id,
                    "agent",
                    input=input_msg if turn_count == 0 else None,
                    stream_mode=["messages", "events"],
                ):
                    event_type = chunk.event
                    data = chunk.data

                    # Handle text tokens
                    if event_type == "messages/partial":
                        for msg in data:
                            if msg.get("type") == "ai" and msg.get("content"):
                                text = msg["content"]
                                if isinstance(text, str):
                                    state.full_response.append(text)
                                    if state.stream:
                                        _write_text(text)

                    # Handle tool calls
                    elif event_type == "messages/complete":
                        for msg in data:
                            if msg.get("type") == "ai":
                                tool_calls = msg.get("tool_calls", [])
                                for tc in tool_calls:
                                    _notify_tool_call(
                                        console,
                                        tc.get("name", "unknown"),
                                        tc.get("args", {}),
                                        quiet=quiet,
                                    )

                turn_count += 1

                # Check for interrupts (HITL)
                thread_state = await client.threads.get_state(thread_id)
                next_tasks = thread_state.get("next", [])

                if not next_tasks:
                    # Agent finished
                    break

                # Handle HITL interrupt
                interrupts = thread_state.get("tasks", [])
                if interrupts:
                    hitl_iterations += 1
                    if hitl_iterations > _MAX_HITL_ITERATIONS:
                        if not quiet:
                            console.print(
                                "[red]HITL iteration limit reached[/red]"
                            )
                        return 1

                    # Auto-resolve all pending interrupts
                    decisions = []
                    for task in interrupts:
                        interrupt_data = task.get("interrupts", [])
                        for interrupt in interrupt_data:
                            tool_name = interrupt.get("value", {}).get(
                                "tool_name", ""
                            )
                            tool_args = interrupt.get("value", {}).get("args", {})

                            approved = _should_auto_approve(
                                tool_name,
                                tool_args,
                                auto_approve=auto_approve,
                                shell_allow_list=shell_allow_list,
                            )
                            decision = "approve" if approved else "reject"
                            decisions.append({"type": decision})

                            if not quiet:
                                icon = "✓" if approved else "✗"
                                style = "green" if approved else "red"
                                console.print(
                                    Text(
                                        f"  {icon} {decision}: {tool_name}",
                                        style=style,
                                    )
                                )

                    # Resume with decisions
                    await client.runs.create(
                        thread_id,
                        "agent",
                        command={
                            "resume": {"decisions": decisions},
                        },
                    )
                    input_msg = None
                    state.interrupt_occurred = True
                    continue

                break

        # Flush buffered response if --no-stream
        if not state.stream and state.full_response:
            _write_text("".join(state.full_response))

        _write_newline()
        return 0

    except KeyboardInterrupt:
        if not quiet:
            console.print("\n[yellow]Interrupted[/yellow]")
        return 130
    except Exception:
        logger.exception("Non-interactive run failed")
        if not quiet:
            console.print_exception()
        return 1
