"""Kubectl read-only DevOps tools for inspecting cluster state."""

from __future__ import annotations

import shlex
from typing import Annotated, Any
from langchain_core.tools import InjectedToolArg, tool
from langchain.tools import ToolRuntime

@tool
def kubectl_get(
    resource: str,
    namespace: str | None = None,
    runtime: Annotated[ToolRuntime[Any, Any] | None, InjectedToolArg()] = None,
) -> dict[str, Any]:
    """Get Kubernetes resources in a read-only manner.

    Args:
        resource: Resource type (e.g. pods, services, deployments).
        namespace: Optional target namespace.
    """
    if runtime is None:
        raise ValueError("runtime is required")
    ns_flag = f"-n {shlex.quote(namespace)}" if namespace else ""
    cmd = f"kubectl get {shlex.quote(resource)} {ns_flag}"
    res = getattr(runtime, "backend").execute(cmd)
    return {"output": res.output, "exit_code": res.exit_code}

@tool
def kubectl_describe(
    resource: str,
    name: str,
    namespace: str | None = None,
    runtime: Annotated[ToolRuntime[Any, Any] | None, InjectedToolArg()] = None,
) -> dict[str, Any]:
    """Describe a Kubernetes resource in detail.

    Args:
        resource: Resource type (e.g. pod, service, deployment).
        name: Name of the resource.
        namespace: Optional target namespace.
    """
    if runtime is None:
        raise ValueError("runtime is required")
    ns_flag = f"-n {shlex.quote(namespace)}" if namespace else ""
    cmd = f"kubectl describe {shlex.quote(resource)} {shlex.quote(name)} {ns_flag}"
    res = getattr(runtime, "backend").execute(cmd)
    return {"output": res.output, "exit_code": res.exit_code}

@tool
def kubectl_logs(
    pod_name: str,
    namespace: str | None = None,
    container: str | None = None,
    runtime: Annotated[ToolRuntime[Any, Any] | None, InjectedToolArg()] = None,
) -> dict[str, Any]:
    """Fetch logs from a specific pod.

    Args:
        pod_name: Name of the pod.
        namespace: Optional target namespace.
        container: Optional specific container in the pod.
    """
    if runtime is None:
        raise ValueError("runtime is required")
    ns_flag = f"-n {shlex.quote(namespace)}" if namespace else ""
    c_flag = f"-c {shlex.quote(container)}" if container else ""
    cmd = f"kubectl logs {shlex.quote(pod_name)} {ns_flag} {c_flag}".strip()
    cmd = " ".join(cmd.split())
    res = getattr(runtime, "backend").execute(cmd)
    return {"output": res.output, "exit_code": res.exit_code}
