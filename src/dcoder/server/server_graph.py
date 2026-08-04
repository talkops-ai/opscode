"""Server-side graph entry point for `langgraph dev`.

This module is referenced by the generated `langgraph.json` and exposes a graph
factory that the LangGraph server can load and serve.

The graph is created by `make_graph()`, which reads configuration from
`ServerConfig.from_env()`.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import traceback
from typing import TYPE_CHECKING, Any

from dcoder.server._server_config import ServerConfig

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

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

    All initialization runs inside a worker thread so blockbuster on the langgraph dev
    server event loop never catches blocking syscalls (os.getcwd, open, stat) on MainThread.
    """

    def _make_graph_sync() -> Any:
        from dcoder.agent.factory import create_dcoder_agent
        from dcoder.config.settings import settings
        from dcoder.model.factory import create_model
        from dcoder.project_utils import get_server_project_context
        from dcoder.tools.catalog import register_all_tools
        from dcoder.tools.registry import ToolRegistry

        config = ServerConfig.from_env()
        project_context = get_server_project_context()

        if project_context is not None:
            settings.reload_from_environment(start_path=project_context.user_cwd)

        model_spec = (
            config.model
            or getattr(settings, "model_name", None)
            or "openai:gpt-4o"
        )

        model_res = create_model(model_spec)
        model_res.apply_to_settings()

        register_all_tools()
        registry = ToolRegistry.get_instance()

        tools: list[Any] = []
        default_tool_names = [
            "web_search",
            "fetch_url",
            "terraform_validate",
            "terraform_plan",
            "terraform_fmt",
            "helm_lint",
            "helm_template",
            "kubectl_get",
            "kubectl_describe",
            "kubectl_logs",
            "ansible_check",
            "argocd_diff",
        ]
        for tool_name in default_tool_names:
            try:
                tools.append(registry.build_tool(tool_name))
            except Exception as e:
                logger.warning("Failed to build registered tool %s: %s", tool_name, e)

        mcp_tools: list[Any] = []
        if not config.no_mcp:
            from dcoder.mcp.discovery import MCPDiscovery
            from dcoder.mcp.trust import compute_config_fingerprint, is_project_mcp_trusted

            discovery = MCPDiscovery()
            mcp_config = discovery.discover()
            if mcp_config:
                project_config_path = (
                    settings.project_root / ".mcp.json" if settings.project_root else None
                )
                trust_project = True
                if project_config_path and project_config_path.exists():
                    fingerprint = compute_config_fingerprint([project_config_path])
                    trust_project = is_project_mcp_trusted(str(settings.project_root), fingerprint)

        if config.enable_interpreter:
            settings.enable_interpreter = True

        agent, _composite_backend = create_dcoder_agent(
            model=model_res.model,
            assistant_id=config.assistant_id,
            tools=tools,
            mcp_tools=mcp_tools,
            sandbox=config.sandbox_type,
            system_prompt=config.system_prompt,
            interactive=config.interactive,
            auto_approve=config.auto_approve,
            enable_shell=config.enable_shell,
            enable_interpreter=config.enable_interpreter,
            cwd=project_context.user_cwd if project_context is not None else config.cwd,
        )
        return agent

    return await asyncio.to_thread(_make_graph_sync)


def _build_graph_factory(
    builder: Callable[[], Awaitable[Any]] | None = None,
) -> Callable[[], Awaitable[Any]]:
    missing = object()
    graph: Any = missing
    lock = asyncio.Lock()

    async def make_graph() -> Any:
        nonlocal graph
        if graph is not missing:
            return graph
        async with lock:
            if graph is missing:
                try:
                    graph = await (builder or _make_graph)()
                except Exception as exc:
                    emit_startup_failure(exc)
                    # Check for credential-related failures so the parent
                    # process captures a descriptive message instead of a
                    # bare exit code.
                    exc_str = str(exc).lower()
                    is_credential_error = any(
                        keyword in exc_str
                        for keyword in (
                            "api_key",
                            "api key",
                            "credential",
                            "authentication",
                            "unauthorized",
                            "missing",
                        )
                    )
                    if is_credential_error:
                        # Re-raise so the parent ServerProcess captures the
                        # exception text and surfaces it via ServerStartFailed,
                        # rather than a bare exit code 3.
                        raise
                    sys.exit(1)
            return graph

    return make_graph


make_graph = _build_graph_factory()
