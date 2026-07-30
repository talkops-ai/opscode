"""ArgoCD DevOps tool to check resource differences."""

from __future__ import annotations

import shlex
from typing import Annotated, Any
from langchain_core.tools import InjectedToolArg, tool
from langchain.tools import ToolRuntime

@tool
def argocd_diff(
    app_name: str,
    runtime: Annotated[ToolRuntime[Any, Any] | None, InjectedToolArg()] = None,
) -> dict[str, Any]:
    """Compare live cluster resources against git configuration for an ArgoCD Application.

    Args:
        app_name: Name of the ArgoCD Application.
    """
    if runtime is None:
        raise ValueError("runtime is required")
    cmd = f"argocd app diff {shlex.quote(app_name)}"
    res = getattr(runtime, "backend").execute(cmd)
    return {"output": res.output, "exit_code": res.exit_code}
