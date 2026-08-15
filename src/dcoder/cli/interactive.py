"""Interactive TUI runner for dcoder.

Launches the Textual ``DCoderApp`` immediately and starts the LangGraph dev
server in the background (deferred startup).  The TUI renders a splash /
welcome screen while the server boots, then transitions to "Ready" once the
``ServerReady`` message arrives.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def run_interactive(
    *,
    model: str | None = None,
    model_params: dict[str, Any] | None = None,
    profile_override: dict[str, Any] | None = None,
    assistant_id: str = "dcoder",
    auto_approve: bool = False,
    resume_thread: str | None = None,
    goal: str | None = None,
    initial_prompt: str | None = None,
    initial_skill: str | None = None,
    startup_cmd: str | None = None,
    shell_allow_list: list[str] | None = None,
    mcp_config_path: str | None = None,
    no_mcp: bool = False,
    trust_project_mcp: bool | None = None,
    enable_interpreter: bool | None = None,
    interpreter_ptc: str | list[str] | None = None,
    allow_fs_tools: str | list[str] | None = "all",
    recursion_limit: int | None = None,
) -> int:
    """Launch the interactive Textual TUI with deferred server startup."""
    import asyncio

    from dcoder.exceptions import NoCredentialsConfiguredError
    from dcoder.model.config import apply_stored_credentials
    from dcoder.model.factory import _get_default_model_spec, detect_provider, normalize_model_spec
    from dcoder.ui.app import DCoderApp

    defer_server_start = False
    try:
        raw_spec = model or _get_default_model_spec()
        model_spec = normalize_model_spec(raw_spec)
        provider = model_spec.split(":", 1)[0] if ":" in model_spec else (detect_provider(model_spec) or "openai")
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
            "profile_override": profile_override,
            "auto_approve": auto_approve,
            "shell_allow_list": shell_allow_list,
            "mcp_config_path": mcp_config_path,
            "no_mcp": no_mcp,
            "trust_project_mcp": trust_project_mcp,
            "enable_interpreter": enable_interpreter,
            "interpreter_ptc": interpreter_ptc,
            "allow_fs_tools": allow_fs_tools,
            "recursion_limit": recursion_limit,
        }

    async def _run() -> int:
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
            initial_prompt=initial_prompt,
            initial_skill=initial_skill,
            startup_cmd=startup_cmd,
            server_kwargs=server_kwargs,
            defer_server_start=defer_server_start,
            mcp_server_info=mcp_server_info,
        )
        return_code = 0
        thread_id = None
        try:
            result = await app.run_async()
            thread_id = result
            return_code = app.return_code or 0
        finally:
            if app._server_proc is not None:
                app._server_proc.stop()

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
