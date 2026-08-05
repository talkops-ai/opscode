"""ArgoCD DevOps tool to check resource differences."""

from __future__ import annotations

import shlex
import subprocess
from typing import Annotated, Any
from langchain_core.tools import tool, BaseTool


def _execute_cmd(backend: Any, cmd: str) -> dict[str, Any]:
    if backend is not None and hasattr(backend, "execute"):
        res = backend.execute(cmd)
        output = getattr(res, "output", str(res))
        exit_code = getattr(res, "exit_code", 0)
        return {"output": output, "exit_code": exit_code}
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    out = (res.stdout + "\n" + res.stderr).strip() or "<no output>"
    return {"output": out, "exit_code": res.returncode}


def create_argocd_diff_tool(backend: Any = None) -> BaseTool:
    @tool
    def argocd_diff(
        app_name: str,
    ) -> dict[str, Any]:
        """Compare live cluster resources against git configuration for an ArgoCD Application.

        Args:
            app_name: Name of the ArgoCD Application.
        """
        cmd = f"argocd app diff {shlex.quote(app_name)}"
        return _execute_cmd(backend, cmd)
    return argocd_diff
