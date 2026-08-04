"""Helm DevOps tools for linting and template rendering."""

from __future__ import annotations

import shlex
from typing import Annotated, Any
from langchain_core.tools import tool
from langchain_core.tools import BaseTool

def create_helm_lint_tool(backend: Any) -> BaseTool:
    @tool
    def helm_lint(
        directory: str,
    ) -> dict[str, Any]:
        """Lint a Helm chart to check for errors and best practices.

        Args:
            directory: Directory containing the Helm chart (Chart.yaml).
        """
        cmd = f"cd {shlex.quote(directory)} && helm lint ."
        res = backend.execute(cmd)
        return {"output": res.output, "exit_code": res.exit_code}
    return helm_lint

def create_helm_template_tool(backend: Any) -> BaseTool:
    @tool
    def helm_template(
        directory: str,
    ) -> dict[str, Any]:
        """Render chart templates locally and display the output.

        Args:
            directory: Directory containing the Helm chart (Chart.yaml).
        """
        cmd = f"cd {shlex.quote(directory)} && helm template ."
        res = backend.execute(cmd)
        return {"output": res.output, "exit_code": res.exit_code}
    return helm_template
