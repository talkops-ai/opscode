"""Helm DevOps tools for linting and template rendering."""

from __future__ import annotations

import shlex
from typing import Annotated, Any
from langchain_core.tools import InjectedToolArg, tool
from langchain.tools import ToolRuntime

@tool
def helm_lint(
    directory: str,
    runtime: Annotated[ToolRuntime[Any, Any] | None, InjectedToolArg()] = None,
) -> dict[str, Any]:
    """Lint a Helm chart to check for errors and best practices.

    Args:
        directory: Directory containing the Helm chart (Chart.yaml).
    """
    if runtime is None:
        raise ValueError("runtime is required")
    cmd = f"cd {shlex.quote(directory)} && helm lint ."
    res = getattr(runtime, "backend").execute(cmd)
    return {"output": res.output, "exit_code": res.exit_code}

@tool
def helm_template(
    directory: str,
    runtime: Annotated[ToolRuntime[Any, Any] | None, InjectedToolArg()] = None,
) -> dict[str, Any]:
    """Render chart templates locally and display the output.

    Args:
        directory: Directory containing the Helm chart (Chart.yaml).
    """
    if runtime is None:
        raise ValueError("runtime is required")
    cmd = f"cd {shlex.quote(directory)} && helm template ."
    res = getattr(runtime, "backend").execute(cmd)
    return {"output": res.output, "exit_code": res.exit_code}
