"""Helm DevOps tools for linting and template rendering."""

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


def create_helm_lint_tool(backend: Any = None) -> BaseTool:
    @tool
    def helm_lint(
        directory: str,
    ) -> dict[str, Any]:
        """Lint a Helm chart to check for errors and best practices.

        Args:
            directory: Directory containing the Helm chart (Chart.yaml).
        """
        cmd = f"cd {shlex.quote(directory)} && helm lint ."
        return _execute_cmd(backend, cmd)
    return helm_lint


def create_helm_template_tool(backend: Any = None) -> BaseTool:
    @tool
    def helm_template(
        directory: str,
    ) -> dict[str, Any]:
        """Render chart templates locally and display the output.

        Args:
            directory: Directory containing the Helm chart (Chart.yaml).
        """
        cmd = f"cd {shlex.quote(directory)} && helm template ."
        return _execute_cmd(backend, cmd)
    return helm_template
