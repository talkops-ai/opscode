"""Terraform DevOps tools for syntax validation, planning, and formatting."""

from __future__ import annotations

import shlex
from typing import Annotated, Any
from langchain_core.tools import InjectedToolArg, tool
from langchain.tools import ToolRuntime

@tool
def terraform_validate(
    directory: str,
    runtime: Annotated[ToolRuntime[Any, Any] | None, InjectedToolArg()] = None,
) -> dict[str, Any]:
    """Validate Terraform syntax in a given directory.

    Args:
        directory: Directory containing Terraform configuration files.
    """
    if runtime is None:
        raise ValueError("runtime is required")
    cmd = f"cd {shlex.quote(directory)} && terraform validate -json"
    res = getattr(runtime, "backend").execute(cmd)
    return {"output": res.output, "exit_code": res.exit_code}

@tool
def terraform_plan(
    directory: str,
    runtime: Annotated[ToolRuntime[Any, Any] | None, InjectedToolArg()] = None,
) -> dict[str, Any]:
    """Generate and show a Terraform execution plan.

    Args:
        directory: Directory containing Terraform configuration files.
    """
    if runtime is None:
        raise ValueError("runtime is required")
    cmd = f"cd {shlex.quote(directory)} && terraform plan -no-color"
    res = getattr(runtime, "backend").execute(cmd)
    return {"output": res.output, "exit_code": res.exit_code}

@tool
def terraform_fmt(
    directory: str,
    runtime: Annotated[ToolRuntime[Any, Any] | None, InjectedToolArg()] = None,
) -> dict[str, Any]:
    """Check if Terraform configuration files are formatted correctly.

    Args:
        directory: Directory containing Terraform configuration files.
    """
    if runtime is None:
        raise ValueError("runtime is required")
    cmd = f"cd {shlex.quote(directory)} && terraform fmt -check -diff"
    res = getattr(runtime, "backend").execute(cmd)
    return {"output": res.output, "exit_code": res.exit_code}
