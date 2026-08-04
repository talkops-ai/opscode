"""Server lifecycle orchestration for dcoder.

Provides ``server_session`` context manager and ``start_server_and_get_agent``
for launching a LangGraph dev server subprocess and returning a RemoteAgent
client.  Replicates the dcode pattern where both interactive and non-interactive
modes connect to a subprocess-hosted graph via ``RemoteAgent``.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator

from dcoder.server._server_config import ServerConfig
from dcoder.server.server import _EPHEMERAL_PORT, ServerProcess

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

_DISTRIBUTION_NAME = "dcoder"
_SERVER_ENV_PREFIX = "DCODER_SERVER_"


# ── Environment helpers ──────────────────────────────────


def _set_or_clear_server_env(name: str, value: str | None) -> None:
    key = f"{_SERVER_ENV_PREFIX}{name}"
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


def _apply_server_config(config: ServerConfig) -> None:
    for suffix, value in config.to_env().items():
        _set_or_clear_server_env(suffix, value)


# ── Workspace scaffolding ────────────────────────────────


def _scaffold_workspace(work_dir: Path) -> None:
    """Prepare the server working directory with all required files."""
    from dcoder.server.server import generate_langgraph_json

    server_graph_src = Path(__file__).parent.parent / "server" / "server_graph.py"
    server_graph_dst = work_dir / "server_graph.py"
    shutil.copy2(server_graph_src, server_graph_dst)

    _write_checkpointer(work_dir)
    _write_pyproject(work_dir)

    generate_langgraph_json(
        work_dir,
        graph_ref="./server_graph.py:make_graph",
        checkpointer_path="./checkpointer.py:create_checkpointer",
    )


def _write_checkpointer(work_dir: Path) -> None:
    from dcoder.config.paths import SESSIONS_DB_PATH

    db_path = SESSIONS_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db_path_env = f"{_SERVER_ENV_PREFIX}DB_PATH"
    os.environ[db_path_env] = str(db_path)

    content = f'''\
"""Persistent SQLite checkpointer for the LangGraph dev server."""

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator


@asynccontextmanager
async def create_checkpointer() -> AsyncGenerator[Any, None]:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    db_path = os.environ.get("{db_path_env}")
    if not db_path:
        raise RuntimeError(
            "{db_path_env} not set. The dcoder CLI must set this "
            "env var before server startup."
        )
    async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
        yield saver
'''
    (work_dir / "checkpointer.py").write_text(content)


def _write_pyproject(work_dir: Path) -> None:
    content = f"""[project]
name = "dcoder-server-runtime"
version = "0.0.1"
requires-python = ">=3.12"
dependencies = [
    "{_runtime_package_dependency()}",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""
    (work_dir / "pyproject.toml").write_text(content)


def _runtime_package_dependency(package_root: Path | None = None) -> str:
    root = package_root or Path(__file__).parent.parent.parent
    if (root / "pyproject.toml").is_file():
        return f"{_DISTRIBUTION_NAME} @ {root.as_uri()}"

    try:
        installed_version = version(_DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return _DISTRIBUTION_NAME
    return f"{_DISTRIBUTION_NAME}=={installed_version}"


# ── MCP config validation ────────────────────────────────


def _preflight_validate_mcp_config(
    *,
    mcp_config_path: str | None,
    no_mcp: bool,
) -> None:
    if no_mcp or not mcp_config_path:
        return

    path = Path(mcp_config_path)
    if not path.is_file():
        raise FileNotFoundError(f"MCP config file not found: {mcp_config_path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "mcpServers" not in data:
            raise ValueError("Root element must contain 'mcpServers' object.")
    except Exception as exc:
        raise ValueError(f"Invalid MCP config at {mcp_config_path}: {exc}") from exc


def _preflight_validate_credentials(
    *,
    model_name: str | None = None,
) -> None:
    """Soft pre-flight check for LLM provider credentials.

    Logs a warning when the most common API-key env vars are absent.
    Does **not** raise — many valid authentication methods (``gcloud``
    Application Default Credentials, auth tokens, service accounts)
    don't use env vars at all.  The server's own startup error handling
    will surface real credential failures with a descriptive message.
    """
    # Determine which provider is in play.
    provider = "openai"
    if model_name:
        if ":" in model_name:
            provider = model_name.split(":", 1)[0].lower()
        elif model_name.startswith("claude") or model_name.startswith("anthropic"):
            provider = "anthropic"
        elif model_name.startswith("gemini") or model_name.startswith("google"):
            provider = "google"

    # google_genai is an alias for google
    if provider in ("google_genai", "google-genai"):
        provider = "google"

    provider_key_map: dict[str, list[str]] = {
        "openai": ["OPENAI_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
        "google": [
            "GOOGLE_API_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GOOGLE_GENAI_API_KEY",
        ],
    }
    env_keys = provider_key_map.get(provider)

    # Unknown provider (custom endpoint, local model, etc.) — skip check.
    if env_keys is None:
        return

    found = any(os.environ.get(k) for k in env_keys)
    if not found:
        keys_str = " or ".join(f"`{k}`" for k in env_keys)
        logger.warning(
            "No %s credential env vars found (%s). "
            "If you authenticate via auth tokens, ADC, or service accounts "
            "this is expected and can be ignored.",
            provider,
            keys_str,
        )


# ── Server start ─────────────────────────────────────────


async def start_server_and_get_agent(
    *,
    assistant_id: str,
    model_name: str | None = None,
    model_params: dict[str, Any] | None = None,
    auto_approve: bool = False,
    shell_allow_list: list[str] | None = None,
    mcp_config_path: str | None = None,
    no_mcp: bool = False,
    trust_project_mcp: bool | None = None,
    interactive: bool = True,
    cwd: str | Path | None = None,
    host: str = "127.0.0.1",
    port: int = _EPHEMERAL_PORT,
) -> tuple[Any, ServerProcess]:
    """Start a LangGraph dev server and return a RemoteAgent client.

    Returns:
        Tuple of (RemoteAgent, ServerProcess).
    """
    from langgraph_sdk import get_client

    _preflight_validate_mcp_config(
        mcp_config_path=mcp_config_path,
        no_mcp=no_mcp,
    )

    _preflight_validate_credentials(model_name=model_name)

    config = ServerConfig.from_cli_args(
        model_name=model_name,
        model_params=model_params,
        assistant_id=assistant_id,
        auto_approve=auto_approve,
        shell_allow_list=shell_allow_list,
        mcp_config_path=mcp_config_path,
        no_mcp=no_mcp,
        trust_project_mcp=trust_project_mcp,
        interactive=interactive,
        cwd=cwd,
    )
    _apply_server_config(config)

    work_dir = Path.home() / ".dcoder" / ".state" / "server"
    work_dir.mkdir(parents=True, exist_ok=True)
    _scaffold_workspace(work_dir)

    server = ServerProcess(
        host=host,
        port=port,
        config_dir=work_dir,
        owns_config_dir=False,
        scaffold=_scaffold_workspace,
    )
    try:
        await server.start()
        await server.wait_for_graph_ready("agent")
    except Exception:
        server.stop()
        raise

    from dcoder.ui.remote_client import RemoteAgent

    agent = RemoteAgent(url=server.url, graph_name="agent")
    return agent, server


# ── Context manager ──────────────────────────────────────


@asynccontextmanager
async def server_session(
    *,
    assistant_id: str = "dcoder",
    model_name: str | None = None,
    model_params: dict[str, Any] | None = None,
    auto_approve: bool = False,
    shell_allow_list: list[str] | None = None,
    mcp_config_path: str | None = None,
    no_mcp: bool = False,
    trust_project_mcp: bool | None = None,
    interactive: bool = True,
    cwd: str | Path | None = None,
    host: str = "127.0.0.1",
    port: int = _EPHEMERAL_PORT,
) -> AsyncGenerator[tuple[Any, ServerProcess], None]:
    """Start a LangGraph dev server, yield (client, server), shut down on exit.

    Usage::

        async with server_session(assistant_id="dcoder") as (client, server):
            # Use client to communicate with the agent graph
            ...
    """
    server_proc: ServerProcess | None = None
    try:
        client, server_proc = await start_server_and_get_agent(
            assistant_id=assistant_id,
            model_name=model_name,
            model_params=model_params,
            auto_approve=auto_approve,
            shell_allow_list=shell_allow_list,
            mcp_config_path=mcp_config_path,
            no_mcp=no_mcp,
            trust_project_mcp=trust_project_mcp,
            interactive=interactive,
            cwd=cwd,
            host=host,
            port=port,
        )
        yield client, server_proc
    finally:
        if server_proc is not None:
            server_proc.stop()
