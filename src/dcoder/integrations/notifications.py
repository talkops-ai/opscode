"""Convenience notification helpers for common agent events.

Thin wrappers around :func:`~dcoder.integrations.hooks.dispatch_hook` and
:func:`~dcoder.integrations.hooks.dispatch_hook_fire_and_forget` that build
the standard payload dicts so callers don't have to assemble them manually.
"""

from __future__ import annotations

from typing import Any

from dcoder.integrations.hooks import (
    dispatch_hook,
    dispatch_hook_fire_and_forget,
)


async def notify_session_start(session_id: str, model: str) -> None:
    """Fire ``session.start`` (awaited)."""
    await dispatch_hook(
        "session.start",
        {"session_id": session_id, "model": model},
    )


async def notify_session_end(session_id: str, duration_s: float) -> None:
    """Fire ``session.end`` (awaited)."""
    await dispatch_hook(
        "session.end",
        {"session_id": session_id, "duration_s": duration_s},
    )


def notify_tool_use(
    tool_name: str,
    tool_id: str,
    tool_args: dict[str, Any] | None = None,
) -> None:
    """Fire ``tool.use`` (fire-and-forget)."""
    dispatch_hook_fire_and_forget(
        "tool.use",
        {
            "tool_name": tool_name,
            "tool_id": tool_id,
            "tool_args": tool_args or {},
        },
    )


def notify_tool_result(
    tool_name: str,
    tool_status: str = "success",
    tool_output: str = "",
) -> None:
    """Fire ``tool.result`` (fire-and-forget)."""
    dispatch_hook_fire_and_forget(
        "tool.result",
        {
            "tool_name": tool_name,
            "tool_status": tool_status,
            "tool_output": tool_output,
        },
    )


async def notify_task_complete(summary: str) -> None:
    """Fire ``task.complete`` (awaited)."""
    await dispatch_hook("task.complete", {"summary": summary})


def notify_deploy_event(
    event_type: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Fire a DevOps deploy event (fire-and-forget).

    Args:
        event_type: One of ``"deploy.start"``, ``"deploy.complete"``,
            ``"terraform.plan"``, ``"terraform.apply"``, ``"helm.install"``,
            ``"kubectl.apply"``.
        details: Additional payload fields.
    """
    dispatch_hook_fire_and_forget(event_type, details or {})
