"""Local shell and filesystem backend wrapper."""

import os
from pathlib import Path
from typing import Any

from deepagents.backends import LocalShellBackend as SDKLocalShellBackend
from dcoder.backend.registry import register_backend
from dcoder.config.manifest import DEVOPS_PRESERVE_ENV_VARS

def _build_shell_env() -> dict[str, str]:
    """Build a curated, secure shell environment containing required variables."""
    safe_keys = {
        "PATH", "HOME", "SHELL", "TERM", "LANG", "USER", "LOGNAME", "PWD",
        "EDITOR", "VISUAL", "LC_ALL", "LOCALE"
    }
    env = {}
    for key in safe_keys:
        if key in os.environ:
            env[key] = os.environ[key]

    # Prepend common binary directories to PATH
    path_val = env.get("PATH", "")
    for tool_dir in ["/usr/local/bin", "~/.local/bin"]:
        expanded = os.path.expanduser(tool_dir)
        if expanded not in path_val:
            path_val = f"{expanded}:{path_val}"
    env["PATH"] = path_val

    # Copy over DevOps-specific and system environment variables
    for key, val in os.environ.items():
        if key in DEVOPS_PRESERVE_ENV_VARS:
            env[key] = val
        elif key.startswith(("TF_VAR_", "ANSIBLE_", "XDG_")):
            env[key] = val

    return env


@register_backend("local")
class LocalShellBackend(SDKLocalShellBackend):
    """Local shell execution and filesystem backend."""
    
    def __init__(
        self,
        root_dir: Path | str,
        virtual_mode: bool = False,
        inherit_env: bool = False,
        env: dict[str, str] | None = None,
        **kwargs: Any,
    ):
        effective_env = env if env is not None else _build_shell_env()
        super().__init__(
            root_dir=Path(root_dir),
            virtual_mode=virtual_mode,
            inherit_env=inherit_env,
            env=effective_env,
            **kwargs,
        )
