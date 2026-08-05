"""Kubectl read-only DevOps tools for inspecting cluster state."""

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


def create_kubectl_get_tool(backend: Any = None) -> BaseTool:
    @tool
    def kubectl_get(
        resource: str,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Get Kubernetes resources in a read-only manner.

        Args:
            resource: Resource type (e.g. pods, services, deployments).
            namespace: Optional target namespace.
        """
        ns_flag = f"-n {shlex.quote(namespace)}" if namespace else ""
        cmd = f"kubectl get {shlex.quote(resource)} {ns_flag}"
        return _execute_cmd(backend, cmd)
    return kubectl_get


def create_kubectl_describe_tool(backend: Any = None) -> BaseTool:
    @tool
    def kubectl_describe(
        resource: str,
        name: str,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Describe a Kubernetes resource in detail.

        Args:
            resource: Resource type (e.g. pod, service, deployment).
            name: Name of the resource.
            namespace: Optional target namespace.
        """
        ns_flag = f"-n {shlex.quote(namespace)}" if namespace else ""
        cmd = f"kubectl describe {shlex.quote(resource)} {shlex.quote(name)} {ns_flag}"
        return _execute_cmd(backend, cmd)
    return kubectl_describe


def create_kubectl_logs_tool(backend: Any = None) -> BaseTool:
    @tool
    def kubectl_logs(
        pod_name: str,
        namespace: str | None = None,
        container: str | None = None,
    ) -> dict[str, Any]:
        """Fetch logs from a specific pod.

        Args:
            pod_name: Name of the pod.
            namespace: Optional target namespace.
            container: Optional specific container in the pod.
        """
        ns_flag = f"-n {shlex.quote(namespace)}" if namespace else ""
        c_flag = f"-c {shlex.quote(container)}" if container else ""
        cmd = f"kubectl logs {shlex.quote(pod_name)} {ns_flag} {c_flag}".strip()
        return _execute_cmd(backend, cmd)
    return kubectl_logs
