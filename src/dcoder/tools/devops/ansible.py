"""Ansible DevOps tool to dry-run playbooks."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
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


def create_ansible_check_tool(backend: Any = None) -> BaseTool:
    @tool
    def ansible_check(
        playbook: str,
        inventory: str | None = None,
    ) -> dict[str, Any]:
        """Dry-run an Ansible playbook to check for errors and changes without executing them.

        Args:
            playbook: Path to the playbook file.
            inventory: Optional path to the inventory file. If omitted, checks for default 'hosts' or 'inventory.ini' in the directory.
        """
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
        return _execute_cmd(backend, cmd)
    return ansible_check
