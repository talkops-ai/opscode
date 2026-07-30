"""Tool-call renderers for DCoder HITL approval widgets.

Each renderer maps a tool name to a display strategy for the approval
menu or card display.
"""

from __future__ import annotations

import difflib
from typing import Any


class ToolRendererResult:
    """Data bag returned by renderers for the approval widget."""

    def __init__(
        self,
        *,
        title: str,
        details: list[str] | None = None,
        diff_lines: list[str] | None = None,
        file_path: str | None = None,
        content_preview: str | None = None,
    ) -> None:
        self.title = title
        self.details = details or []
        self.diff_lines = diff_lines
        self.file_path = file_path
        self.content_preview = content_preview


def render_tool_approval(
    tool_name: str,
    args: dict[str, Any],
) -> ToolRendererResult:
    """Build approval display data for a tool call."""
    renderer = _RENDERER_REGISTRY.get(tool_name, _render_generic)
    return renderer(tool_name, args)


def _render_generic(tool_name: str, args: dict[str, Any]) -> ToolRendererResult:
    details = [f"{k}: {v}" for k, v in args.items()]
    return ToolRendererResult(title=tool_name, details=details)


def _render_execute(tool_name: str, args: dict[str, Any]) -> ToolRendererResult:
    cmd = args.get("command", "")
    return ToolRendererResult(title=f"Shell: {tool_name}", details=[f"$ {cmd}"])


def _render_write_file(tool_name: str, args: dict[str, Any]) -> ToolRendererResult:
    file_path = args.get("file_path", "")
    content = args.get("content", "")
    ext = file_path.rsplit(".", 1)[-1] if "." in file_path else "text"
    preview = content[:500] + (f"\n... ({len(content) - 500} more chars)" if len(content) > 500 else "")
    return ToolRendererResult(
        title=f"Write: {file_path}",
        file_path=file_path,
        content_preview=preview,
        details=[f"Extension: {ext}", f"Size: {len(content)} chars"],
    )


def _render_edit_file(tool_name: str, args: dict[str, Any]) -> ToolRendererResult:
    file_path = args.get("file_path", "")
    old_string = args.get("old_string", "")
    new_string = args.get("new_string", "")
    diff_lines: list[str] = []
    if old_string or new_string:
        old_lines = old_string.split("\n") if old_string else []
        new_lines = new_string.split("\n") if new_string else []
        raw_diff = list(
            difflib.unified_diff(
                old_lines, new_lines, fromfile="before", tofile="after", lineterm="", n=3
            )
        )
        diff_lines = raw_diff[2:] if len(raw_diff) > 2 else raw_diff
    return ToolRendererResult(
        title=f"Edit: {file_path}", file_path=file_path, diff_lines=diff_lines
    )


def _render_delete_file(tool_name: str, args: dict[str, Any]) -> ToolRendererResult:
    path = str(args.get("file_path") or args.get("path") or "")
    return ToolRendererResult(
        title=f"Delete: {path}", file_path=path, details=["This will permanently delete the file."]
    )


def _render_terraform(tool_name: str, args: dict[str, Any]) -> ToolRendererResult:
    dir_path = args.get("dir", ".")
    action = "plan" if "plan" in tool_name else "apply"
    return ToolRendererResult(
        title=f"🏗️ Terraform {action.upper()}: {dir_path}",
        details=[f"Directory: {dir_path}", f"Action: terraform {action}"],
    )


def _render_kubectl(tool_name: str, args: dict[str, Any]) -> ToolRendererResult:
    resource = args.get("resource", "manifest")
    ns = args.get("namespace", "default")
    return ToolRendererResult(
        title=f"⎈ Kubectl: {tool_name}",
        details=[f"Resource: {resource}", f"Namespace: {ns}"],
    )


def _render_helm(tool_name: str, args: dict[str, Any]) -> ToolRendererResult:
    release = args.get("release", "release")
    chart = args.get("chart", "chart")
    return ToolRendererResult(
        title=f"☸️ Helm: {tool_name}",
        details=[f"Release: {release}", f"Chart: {chart}"],
    )


def _render_ansible(tool_name: str, args: dict[str, Any]) -> ToolRendererResult:
    playbook = args.get("playbook", "playbook.yml")
    inventory = args.get("inventory", "hosts")
    return ToolRendererResult(
        title=f"🅰️ Ansible: {tool_name}",
        details=[f"Playbook: {playbook}", f"Inventory: {inventory}"],
    )


_RENDERER_REGISTRY: dict[str, Any] = {
    "execute": _render_execute,
    "bash": _render_execute,
    "shell": _render_execute,
    "write_file": _render_write_file,
    "edit_file": _render_edit_file,
    "delete": _render_delete_file,
    "terraform_plan": _render_terraform,
    "terraform_apply": _render_terraform,
    "kubectl_apply": _render_kubectl,
    "kubectl_delete": _render_kubectl,
    "helm_install": _render_helm,
    "helm_upgrade": _render_helm,
    "ansible_playbook": _render_ansible,
}
