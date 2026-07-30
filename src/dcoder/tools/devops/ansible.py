"""Ansible DevOps tool to dry-run playbooks."""

from __future__ import annotations

import shlex
from typing import Annotated, Any
from langchain_core.tools import InjectedToolArg, tool
from langchain.tools import ToolRuntime

@tool
def ansible_check(
    playbook: str,
    inventory: str | None = None,
    runtime: Annotated[ToolRuntime[Any, Any] | None, InjectedToolArg()] = None,
) -> dict[str, Any]:
    """Dry-run an Ansible playbook to check for errors and changes without executing them.

    Args:
        playbook: Path to the playbook file.
        inventory: Optional path to the inventory file. If omitted, checks for default 'hosts' or 'inventory.ini' in the directory.
    """
    if runtime is None:
        raise ValueError("runtime is required")
    from pathlib import Path
    if not inventory:
        # Check for default inventory files
        for candidate in ["hosts", "inventory.ini"]:
            p = Path(playbook).parent / candidate
            if p.exists():
                inventory = str(p)
                break
    inv_flag = f"-i {shlex.quote(inventory)}" if inventory else ""
    cmd = f"ansible-playbook {shlex.quote(playbook)} {inv_flag} --check".strip()
    cmd = " ".join(cmd.split())
    res = getattr(runtime, "backend").execute(cmd)
    return {"output": res.output, "exit_code": res.exit_code}
