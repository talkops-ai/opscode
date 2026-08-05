"""Terraform DevOps tools for syntax validation, planning, and formatting."""

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


def create_terraform_validate_tool(backend: Any = None) -> BaseTool:
    @tool
    def terraform_validate(
        directory: str,
    ) -> dict[str, Any]:
        """Validate Terraform syntax in a given directory.

        Args:
            directory: Directory containing Terraform configuration files.
        """
        cmd = f"cd {shlex.quote(directory)} && terraform validate -json"
        return _execute_cmd(backend, cmd)
    return terraform_validate


def create_terraform_plan_tool(backend: Any = None) -> BaseTool:
    @tool
    def terraform_plan(
        directory: str,
    ) -> dict[str, Any]:
        """Generate and show a Terraform execution plan.

        Args:
            directory: Directory containing Terraform configuration files.
        """
        cmd = f"cd {shlex.quote(directory)} && terraform plan -no-color"
        return _execute_cmd(backend, cmd)
    return terraform_plan


def create_terraform_fmt_tool(backend: Any = None) -> BaseTool:
    @tool
    def terraform_fmt(
        directory: str,
    ) -> dict[str, Any]:
        """Check if Terraform configuration files are formatted correctly.

        Args:
            directory: Directory containing Terraform configuration files.
        """
        cmd = f"cd {shlex.quote(directory)} && terraform fmt -check -diff"
        return _execute_cmd(backend, cmd)
    return terraform_fmt
