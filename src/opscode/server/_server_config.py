"""Typed configuration for the app-to-server subprocess communication channel.

The app spawns a `langgraph dev` subprocess and passes configuration via
environment variables prefixed with `OPSCODE_SERVER_`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opscode.config.manifest import DEFAULT_AGENT_NAME as DEFAULT_ASSISTANT_ID
from opscode.server import SERVER_ENV_PREFIX


def _read_env_bool(suffix: str, *, default: bool = False) -> bool:
    raw = os.environ.get(f"{SERVER_ENV_PREFIX}{suffix}")
    if raw is None:
        return default
    return raw.lower() == "true"


def _read_env_json(suffix: str) -> Any:
    raw = os.environ.get(f"{SERVER_ENV_PREFIX}{suffix}")
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = (
            f"Failed to parse {SERVER_ENV_PREFIX}{suffix} as JSON: {exc}. "
            f"Value was: {raw[:200]!r}"
        )
        raise ValueError(msg) from exc


def _read_env_str(suffix: str) -> str | None:
    return os.environ.get(f"{SERVER_ENV_PREFIX}{suffix}")


def _read_env_int(suffix: str, *, default: int | None) -> int | None:
    raw = os.environ.get(f"{SERVER_ENV_PREFIX}{suffix}")
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _read_env_optional_bool(suffix: str) -> bool | None:
    raw = os.environ.get(f"{SERVER_ENV_PREFIX}{suffix}")
    if raw is None:
        return None
    return raw.lower() == "true"


def _read_env_allow_fs_tools() -> list[str] | None:
    env_name = f"{SERVER_ENV_PREFIX}ALLOW_FS_TOOLS"
    if env_name not in os.environ:
        return None
    raw = _read_env_json("ALLOW_FS_TOOLS")
    if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
        return raw
    return None


def _resolve_enable_interpreter(
    enable_interpreter: bool | None, sandbox_type: str | None
) -> bool:
    if enable_interpreter is not None:
        return enable_interpreter
    if sandbox_type and sandbox_type != "none":
        return False

    from opscode.config.settings import settings
    return settings.enable_interpreter


def _interpreter_suppressed_by_sandbox(
    *, enable_interpreter: bool | None, sandbox_type: str | None, local_default: bool
) -> bool:
    if enable_interpreter is not None:
        return False
    if not (sandbox_type and sandbox_type != "none"):
        return False
    return local_default


@dataclass(frozen=True)
class ServerConfig:
    """Full configuration payload passed from the app to the server subprocess."""

    model: str | None = None
    model_params: dict[str, Any] | None = None
    profile_override: dict[str, Any] | None = None
    assistant_id: str = DEFAULT_ASSISTANT_ID
    system_prompt: str | None = None
    auto_approve: bool = False
    interrupt_shell_only: bool = False
    shell_allow_list: list[str] | None = None
    interactive: bool = True
    enable_shell: bool = True
    enable_ask_user: bool = False
    enable_memory: bool = True
    enable_skills: bool = True
    enable_interpreter: bool = True
    interpreter_ptc: str | list[str] | None = "safe"
    interpreter_ptc_acknowledge_unsafe: bool = False
    allow_fs_tools: list[str] | None = None
    recursion_limit: int | None = None
    user_langchain_project: str | None = "opscode"
    rubric_model: str | None = None
    rubric_max_iterations: int | None = None
    sandbox_type: str | None = None
    sandbox_id: str | None = None
    sandbox_snapshot_name: str | None = None
    sandbox_setup: str | None = None
    cwd: str | None = None
    project_root: str | None = None
    mcp_config_path: str | None = None
    no_mcp: bool = False
    trust_project_mcp: bool | None = None

    def __post_init__(self) -> None:
        if self.sandbox_type == "none":
            object.__setattr__(self, "sandbox_type", None)
        if self.shell_allow_list is not None and len(self.shell_allow_list) == 0:
            msg = "shell_allow_list must be None or non-empty"
            raise ValueError(msg)
        if isinstance(self.rubric_max_iterations, bool):
            msg = "rubric_max_iterations must be None or a positive integer"
            raise TypeError(msg)
        if self.rubric_max_iterations is not None and self.rubric_max_iterations <= 0:
            msg = "rubric_max_iterations must be None or a positive integer"
            raise ValueError(msg)

    def to_env(self) -> dict[str, str | None]:
        return {
            "MODEL": self.model,
            "MODEL_PARAMS": (
                json.dumps(self.model_params) if self.model_params is not None else None
            ),
            "PROFILE_OVERRIDE": (
                json.dumps(self.profile_override) if self.profile_override is not None else None
            ),
            "ASSISTANT_ID": self.assistant_id,
            "SYSTEM_PROMPT": self.system_prompt,
            "AUTO_APPROVE": str(self.auto_approve).lower(),
            "INTERRUPT_SHELL_ONLY": str(self.interrupt_shell_only).lower(),
            "SHELL_ALLOW_LIST": (
                ",".join(self.shell_allow_list)
                if self.shell_allow_list is not None
                else None
            ),
            "INTERACTIVE": str(self.interactive).lower(),
            "ENABLE_SHELL": str(self.enable_shell).lower(),
            "ENABLE_ASK_USER": str(self.enable_ask_user).lower(),
            "ENABLE_MEMORY": str(self.enable_memory).lower(),
            "ENABLE_SKILLS": str(self.enable_skills).lower(),
            "ENABLE_INTERPRETER": str(self.enable_interpreter).lower(),
            "INTERPRETER_PTC": (
                json.dumps(self.interpreter_ptc)
                if self.interpreter_ptc is not None
                else None
            ),
            "INTERPRETER_PTC_ACKNOWLEDGE_UNSAFE": str(
                self.interpreter_ptc_acknowledge_unsafe
            ).lower(),
            "ALLOW_FS_TOOLS": (
                json.dumps(self.allow_fs_tools)
                if self.allow_fs_tools is not None
                else None
            ),
            "RECURSION_LIMIT": (
                str(self.recursion_limit)
                if self.recursion_limit is not None
                else None
            ),
            "RUBRIC_MODEL": self.rubric_model,
            "RUBRIC_MAX_ITERATIONS": (
                str(self.rubric_max_iterations)
                if self.rubric_max_iterations is not None
                else None
            ),
            "SANDBOX_TYPE": self.sandbox_type,
            "SANDBOX_ID": self.sandbox_id,
            "SANDBOX_SNAPSHOT_NAME": self.sandbox_snapshot_name,
            "SANDBOX_SETUP": self.sandbox_setup,
            "CWD": self.cwd,
            "PROJECT_ROOT": self.project_root,
            "MCP_CONFIG_PATH": self.mcp_config_path,
            "NO_MCP": str(self.no_mcp).lower(),
            "TRUST_PROJECT_MCP": (
                str(self.trust_project_mcp).lower()
                if self.trust_project_mcp is not None
                else None
            ),
        }

    @classmethod
    def from_env(cls) -> ServerConfig:
        return cls(
            model=_read_env_str("MODEL"),
            model_params=_read_env_json("MODEL_PARAMS"),
            profile_override=_read_env_json("PROFILE_OVERRIDE"),
            assistant_id=_read_env_str("ASSISTANT_ID") or DEFAULT_ASSISTANT_ID,
            system_prompt=_read_env_str("SYSTEM_PROMPT"),
            auto_approve=_read_env_bool("AUTO_APPROVE"),
            interrupt_shell_only=_read_env_bool("INTERRUPT_SHELL_ONLY"),
            shell_allow_list=(
                [cmd.strip() for cmd in raw.split(",") if cmd.strip()]
                if (raw := _read_env_str("SHELL_ALLOW_LIST"))
                else None
            )
            or None,
            interactive=_read_env_bool("INTERACTIVE", default=True),
            enable_shell=_read_env_bool("ENABLE_SHELL", default=True),
            enable_ask_user=_read_env_bool("ENABLE_ASK_USER"),
            enable_memory=_read_env_bool("ENABLE_MEMORY", default=True),
            enable_skills=_read_env_bool("ENABLE_SKILLS", default=True),
            enable_interpreter=_read_env_bool("ENABLE_INTERPRETER", default=True),
            interpreter_ptc=(
                _read_env_json("INTERPRETER_PTC") 
                if _read_env_json("INTERPRETER_PTC") is not None 
                else "safe"
            ),
            interpreter_ptc_acknowledge_unsafe=_read_env_bool(
                "INTERPRETER_PTC_ACKNOWLEDGE_UNSAFE"
            ),
            allow_fs_tools=_read_env_allow_fs_tools(),
            recursion_limit=_read_env_int("RECURSION_LIMIT", default=None),
            user_langchain_project=_read_env_str("USER_LANGCHAIN_PROJECT") or "opscode",
            rubric_model=_read_env_str("RUBRIC_MODEL") or None,
            rubric_max_iterations=_read_env_int("RUBRIC_MAX_ITERATIONS", default=None),
            sandbox_type=_read_env_str("SANDBOX_TYPE"),
            sandbox_id=_read_env_str("SANDBOX_ID"),
            sandbox_snapshot_name=_read_env_str("SANDBOX_SNAPSHOT_NAME") or None,
            sandbox_setup=_read_env_str("SANDBOX_SETUP"),
            cwd=_read_env_str("CWD"),
            project_root=_read_env_str("PROJECT_ROOT"),
            mcp_config_path=_read_env_str("MCP_CONFIG_PATH"),
            no_mcp=_read_env_bool("NO_MCP"),
            trust_project_mcp=_read_env_optional_bool("TRUST_PROJECT_MCP"),
        )

    @classmethod
    def from_cli_args(
        cls,
        *,
        model_name: str | None = None,
        model_params: dict[str, Any] | None = None,
        profile_override: dict[str, Any] | None = None,
        assistant_id: str = DEFAULT_ASSISTANT_ID,
        auto_approve: bool = False,
        shell_allow_list: list[str] | None = None,
        mcp_config_path: str | None = None,
        no_mcp: bool = False,
        trust_project_mcp: bool | None = None,
        enable_interpreter: bool | None = None,
        interpreter_ptc: str | list[str] | None = "safe",
        allow_fs_tools: str | list[str] | None = None,
        recursion_limit: int | None = None,
        interactive: bool = True,
        cwd: str | Path | None = None,
    ) -> ServerConfig:
        """Build a ServerConfig from CLI-provided arguments."""
        from opscode.project_utils import ProjectContext

        user_cwd = Path(cwd).expanduser().resolve() if cwd is not None else Path.cwd()
        project_context = ProjectContext.from_user_cwd(user_cwd)

        # Resolve MCP config path if provided
        normalized_mcp: str | None = None
        if mcp_config_path:
            try:
                normalized_mcp = str(Path(mcp_config_path).expanduser().resolve())
            except OSError:
                normalized_mcp = mcp_config_path

        resolved_interpreter = enable_interpreter if enable_interpreter is not None else True

        # Resolve allow_fs_tools: "all" or None collapses to None (unrestricted)
        resolved_fs_tools: list[str] | None = None
        if isinstance(allow_fs_tools, list):
            resolved_fs_tools = allow_fs_tools
        elif isinstance(allow_fs_tools, str) and allow_fs_tools.strip().lower() != "all":
            resolved_fs_tools = [x.strip() for x in allow_fs_tools.split(",") if x.strip()]

        return cls(
            model=model_name,
            model_params=model_params,
            profile_override=profile_override,
            assistant_id=assistant_id,
            auto_approve=auto_approve,
            shell_allow_list=shell_allow_list,
            enable_interpreter=resolved_interpreter,
            interpreter_ptc=interpreter_ptc,
            allow_fs_tools=resolved_fs_tools,
            recursion_limit=recursion_limit,
            interactive=interactive,
            cwd=str(project_context.user_cwd),
            project_root=str(project_context.project_root) if project_context.project_root else None,
            mcp_config_path=normalized_mcp,
            no_mcp=no_mcp,
            trust_project_mcp=trust_project_mcp,
        )


