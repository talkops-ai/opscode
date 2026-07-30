"""Interactive TUI runner for dcoder.

Launches the Textual ``DCoderApp`` immediately and starts the LangGraph dev
server in the background (deferred startup).  The TUI renders a splash /
welcome screen while the server boots, then transitions to "Ready" once the
``ServerReady`` message arrives.  This mirrors the dcode architecture where
the user sees instant first paint rather than a blank terminal.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def run_interactive(
    *,
    model: str | None = None,
    model_params: dict[str, Any] | None = None,
    assistant_id: str = "dcoder",
    auto_approve: bool = False,
    resume_thread: str | None = None,
    goal: str | None = None,
    shell_allow_list: list[str] | None = None,
    mcp_config_path: str | None = None,
    no_mcp: bool = False,
    trust_project_mcp: bool | None = None,
) -> int:
    """Launch the interactive Textual TUI with deferred server startup.

    Instead of blocking until the LangGraph server is healthy (which takes
    5–10 seconds), the TUI is started immediately.  Server startup happens
    in a background worker inside ``DCoderApp.on_mount``.

    Args:
        model: Model identifier (e.g. ``"anthropic:claude-sonnet-4"``).
        model_params: Extra model parameters as a dict.
        assistant_id: Agent identity.
        auto_approve: Whether to auto-approve all tool calls.
        resume_thread: Thread ID to resume, or ``None`` for new.
        goal: Goal text for acceptance criteria.
        shell_allow_list: Allowed shell commands.
        mcp_config_path: Path to MCP config file.
        no_mcp: Disable all MCP servers.
        trust_project_mcp: Auto-trust project MCP servers.

    Returns:
        Process exit code (0 for success).
    """
    import asyncio

    from dcoder.exceptions import NoCredentialsConfiguredError
    from dcoder.model.factory import _get_default_model_spec
    from dcoder.model.config import apply_stored_credentials
    from dcoder.ui.app import DCoderApp

    defer_server_start = False
    try:
        model_spec = model or _get_default_model_spec()
        provider = model_spec.split(":")[0] if ":" in model_spec else "google_genai"
        apply_stored_credentials(provider)
    except NoCredentialsConfiguredError:
        model_spec = ""
        defer_server_start = True

    server_kwargs: dict[str, Any] | None = None
    if not defer_server_start:
        server_kwargs = {
            "assistant_id": assistant_id,
            "model_name": model_spec,
            "model_params": model_params,
            "auto_approve": auto_approve,
            "shell_allow_list": shell_allow_list,
            "mcp_config_path": mcp_config_path,
            "no_mcp": no_mcp,
            "trust_project_mcp": trust_project_mcp,
        }

    async def _run() -> int:
        # Preload MCP server metadata for the /mcp viewer.
        # Opens temporary sessions to discover tools, then closes them.
        from dcoder.mcp.preload import preload_mcp_server_info

        mcp_server_info = None
        if not no_mcp:
            try:
                mcp_server_info = await preload_mcp_server_info(
                    mcp_config_path=mcp_config_path,
                    no_mcp=no_mcp,
                )
            except Exception:
                logger.warning("MCP metadata preload failed", exc_info=True)

        app = DCoderApp(
            assistant_id=assistant_id,
            model=model_spec,
            auto_approve=auto_approve,
            resume_thread=resume_thread,
            goal=goal,
            server_kwargs=server_kwargs,
            defer_server_start=defer_server_start,
            mcp_server_info=mcp_server_info,
        )
        return_code = 0
        thread_id = None
        try:
            # run_async() returns the value passed to app.exit(result=...)
            # which is the thread_id string (set in our exit override).
            result = await app.run_async()
            thread_id = result  # raw thread_id string or None
            return_code = app.return_code or 0
        finally:
            # Guarantee server cleanup regardless of how the app exits.
            if app._server_proc is not None:
                app._server_proc.stop()

        # Print resume hint on clean exit (matching dcode)
        if thread_id and return_code == 0:
            try:
                from rich.console import Console
                from rich.text import Text

                console = Console()
                console.print()
                console.print("[dim]Resume this thread with:[/dim]")
                hint = Text("dcoder -r ", style="cyan")
                hint.append(str(thread_id), style="cyan")
                console.print(hint)
            except Exception:
                logger.debug("Failed to print resume hint", exc_info=True)

        return return_code

    return asyncio.run(_run())
