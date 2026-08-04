"""ArgoCD DevOps tool to check resource differences."""

from __future__ import annotations

import shlex
from typing import Annotated, Any
from langchain_core.tools import tool
from langchain_core.tools import BaseTool

def create_argocd_diff_tool(backend: Any) -> BaseTool:
    @tool
    def argocd_diff(
        app_name: str,
    ) -> dict[str, Any]:
        """Compare live cluster resources against git configuration for an ArgoCD Application.

        Args:
            app_name: Name of the ArgoCD Application.
        """
        cmd = f"argocd app diff {shlex.quote(app_name)}"
        res = backend.execute(cmd)
        return {"output": res.output, "exit_code": res.exit_code}
    return argocd_diff
