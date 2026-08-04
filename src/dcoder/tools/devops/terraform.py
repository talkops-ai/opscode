"""Terraform DevOps tools for syntax validation, planning, and formatting."""

from __future__ import annotations

import shlex
from typing import Annotated, Any
from langchain_core.tools import tool
from langchain_core.tools import BaseTool

def create_terraform_validate_tool(backend: Any) -> BaseTool:
    @tool
    def terraform_validate(
        directory: str,
    ) -> dict[str, Any]:
        """Validate Terraform syntax in a given directory.

        Args:
            directory: Directory containing Terraform configuration files.
        """
        cmd = f"cd {shlex.quote(directory)} && terraform validate -json"
        res = backend.execute(cmd)
        return {"output": res.output, "exit_code": res.exit_code}
    return terraform_validate

def create_terraform_plan_tool(backend: Any) -> BaseTool:
    @tool
    def terraform_plan(
        directory: str,
    ) -> dict[str, Any]:
        """Generate and show a Terraform execution plan.

        Args:
            directory: Directory containing Terraform configuration files.
        """
        cmd = f"cd {shlex.quote(directory)} && terraform plan -no-color"
        res = backend.execute(cmd)
        return {"output": res.output, "exit_code": res.exit_code}
    return terraform_plan

def create_terraform_fmt_tool(backend: Any) -> BaseTool:
    @tool
    def terraform_fmt(
        directory: str,
    ) -> dict[str, Any]:
        """Check if Terraform configuration files are formatted correctly.

        Args:
            directory: Directory containing Terraform configuration files.
        """
        cmd = f"cd {shlex.quote(directory)} && terraform fmt -check -diff"
        res = backend.execute(cmd)
        return {"output": res.output, "exit_code": res.exit_code}
    return terraform_fmt
