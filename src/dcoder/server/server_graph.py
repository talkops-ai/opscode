"""Server-side graph entry point for `langgraph dev`.

This module is referenced by the generated `langgraph.json` and exposes a graph
factory that the LangGraph server can load and serve.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import traceback
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from dcoder.server import SERVER_ENV_PREFIX
from dcoder.server._server_config import ServerConfig

logger = logging.getLogger(__name__)

# Machine-readable prefix for startup errors
_STARTUP_ERROR_MARKER = "DCODER_STARTUP_ERROR:"


def emit_startup_failure(exc: BaseException) -> None:
    """Report a server graph startup failure to the parent app process."""
    logger.critical("Failed to initialize server graph", exc_info=exc)
    print(
        f"Failed to initialize server graph: {exc}\n{traceback.format_exc()}",
        file=sys.stderr,
    )
    exc_lines = str(exc).splitlines()
    summary = exc_lines[0] if exc_lines else "<no message>"
    print(
        f"{_STARTUP_ERROR_MARKER}{type(exc).__name__}: {summary}",
        file=sys.stderr,
    )


async def _make_graph() -> Any:
    """Create the agent graph from environment-based configuration.

    All blocking work (env reads, os.getcwd, file I/O, settings loading,
    model resolution) runs inside ``asyncio.to_thread`` because the
    ``langgraph-api`` inmem runtime uses *blockbuster* to forbid blocking
    syscalls on the async event loop.
    """

    def _create():
        import os
        from pathlib import Path
        from dcoder.config.settings import _load_dotenv, settings
        from dcoder.model.config import apply_stored_credentials

        _load_dotenv(refresh_loaded=True)
        config = ServerConfig.from_env()

        # Resolve project working directory from server env
        user_cwd_raw = os.environ.get(f"{SERVER_ENV_PREFIX}CWD")
        user_cwd = Path(user_cwd_raw) if user_cwd_raw else None

        if user_cwd is not None:
            settings.reload_from_environment(start_path=user_cwd)

        # Apply configuration to settings
        if config.shell_allow_list is not None:
            settings.shell_allow_list = config.shell_allow_list

        tools: list = []
        reasoning_eff = os.environ.get("DCODER_REASONING_EFFORT") or os.environ.get("DCODER_SERVER_REASONING_EFFORT")
        if reasoning_eff:
            settings.reasoning_effort = reasoning_eff

        model_spec = (
            config.model
            or os.environ.get("DCODER_SERVER_MODEL")
            or os.environ.get("DCODER_MODEL_NAME")
            or settings.model_name
            or "openai:gpt-4o"
        )
        provider = model_spec.split(":", 1)[0] if ":" in model_spec else "openai"
        apply_stored_credentials(provider)

        logger.info(
            "Initializing Server Graph Agent: model_spec=%s, GOOGLE_API_KEY_set=%s, VERTEXAI=%s",
            model_spec,
            bool(os.environ.get("GOOGLE_API_KEY")),
            os.environ.get("GOOGLE_GENAI_USE_VERTEXAI"),
        )

        from dcoder.agent.factory import create_dcoder_agent

        agent, _ = create_dcoder_agent(
            model=model_spec,
            assistant_id=config.assistant_id,
            tools=tools,
            system_prompt=config.system_prompt,
            interactive=config.interactive,
            auto_approve=config.auto_approve,
            enable_shell=config.enable_shell,
            cwd=user_cwd or config.cwd,
            sandbox=config.sandbox_type,
        )
        return agent

    return await asyncio.to_thread(_create)


def _build_graph_factory() -> Callable[[], Awaitable[Any]]:
    cached_graph: Any = None
    cached_key: tuple[str, str | None, str | None] | None = None
    lock = asyncio.Lock()

    async def make_graph() -> Any:
        nonlocal cached_graph, cached_key

        def _get_key():
            import os
            from dcoder.config.settings import _load_dotenv, settings, resolve_env_var
            from dcoder.model.config import apply_stored_credentials

            _load_dotenv(refresh_loaded=True)
            model_spec = (
                os.environ.get("DCODER_SERVER_MODEL")
                or os.environ.get("DCODER_MODEL_NAME")
                or settings.model_name
                or "openai:gpt-4o"
            )
            provider = model_spec.split(":", 1)[0] if ":" in model_spec else "openai"
            apply_stored_credentials(provider)
            key_val = (
                resolve_env_var(f"{provider.upper()}_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
                or os.environ.get("OPENAI_API_KEY")
                or os.environ.get("ANTHROPIC_API_KEY")
            )
            vertex_val = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI")
            return (model_spec, key_val, vertex_val)

        current_key = await asyncio.to_thread(_get_key)

        if cached_graph is not None and cached_key == current_key:
            return cached_graph

        async with lock:
            if cached_graph is None or cached_key != current_key:
                try:
                    cached_graph = await _make_graph()
                    cached_key = current_key
                except Exception as exc:
                    emit_startup_failure(exc)
                    sys.exit(1)
            return cached_graph

    return make_graph


make_graph = _build_graph_factory()
