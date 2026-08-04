"""Kubectl read-only DevOps tools for inspecting cluster state."""

from __future__ import annotations

import shlex
from typing import Annotated, Any
from langchain_core.tools import tool
from langchain_core.tools import BaseTool

def create_kubectl_get_tool(backend: Any) -> BaseTool:
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
        res = backend.execute(cmd)
        return {"output": res.output, "exit_code": res.exit_code}
    return kubectl_get

def create_kubectl_describe_tool(backend: Any) -> BaseTool:
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
        res = backend.execute(cmd)
        return {"output": res.output, "exit_code": res.exit_code}
    return kubectl_describe

def create_kubectl_logs_tool(backend: Any) -> BaseTool:
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
        cmd = " ".join(cmd.split())
        res = backend.execute(cmd)
        return {"output": res.output, "exit_code": res.exit_code}
    return kubectl_logs
