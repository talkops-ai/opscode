"""Event hook dispatch for dcoder.

Hooks allow external tools to react to agent events.  Configured in
``~/.dcoder/hooks.json``::

    {
      "hooks": [
        {
          "command": ["bash", "notify.sh"],
          "events": ["session.start", "task.complete"]
        },
        {
          "command": ["python", "audit.py"],
          "events": []
        }
      ]
    }

An empty ``events`` list means *all* events.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess  # noqa: S404
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────

HOOK_SUBPROCESS_TIMEOUT = 5
"""Seconds before a hook subprocess is killed."""

HOOK_TOOL_OUTPUT_LIMIT = 2000
"""Max chars kept in ``tool_output`` payload fields."""

# Standard events (from doc-12 §2.2)
STANDARD_EVENTS = frozenset(
    {
        "session.start",
        "session.end",
        "user.prompt",
        "tool.use",
        "tool.result",
        "tool.error",
        "task.complete",
        "user.name.set",
        "context.compact",
        "permission.request",
    }
)

# DevOps-specific events
DEVOPS_EVENTS = frozenset(
    {
        "terraform.plan",
        "terraform.apply",
        "helm.install",
        "kubectl.apply",
        "deploy.start",
        "deploy.complete",
    }
)

ALL_KNOWN_EVENTS = STANDARD_EVENTS | DEVOPS_EVENTS


# ── Hook config ──────────────────────────────────────────


@dataclass(frozen=True)
class HookConfig:
    """A single hook definition from ``hooks.json``."""

    command: list[str]
    """Subprocess command to execute."""

    events: frozenset[str]
    """Events this hook listens to.  Empty → all events."""

    def matches(self, event: str) -> bool:
        """Return ``True`` if this hook should fire for *event*."""
        return len(self.events) == 0 or event in self.events


# ── Internal state ───────────────────────────────────────

_hooks: list[HookConfig] = []
_pending_tasks: set[asyncio.Task[None]] = set()
_loaded = False


# ── Config loading ───────────────────────────────────────


def _default_hooks_path() -> Path:
    """Return ``~/.dcoder/hooks.json``."""
    return Path.home() / ".dcoder" / "hooks.json"


def load_hooks(path: Path | None = None) -> list[HookConfig]:
    """Parse ``hooks.json`` and populate the module-level hook list.

    Args:
        path: Explicit path.  Falls back to ``~/.dcoder/hooks.json``.

    Returns:
        The parsed list (also stored at module level).
    """
    global _hooks, _loaded  # noqa: PLW0603

    hooks_file = path or _default_hooks_path()
    if not hooks_file.is_file():
        _hooks = []
        _loaded = True
        return _hooks

    try:
        data = json.loads(hooks_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to parse hooks config %s: %s", hooks_file, exc)
        _hooks = []
        _loaded = True
        return _hooks

    parsed: list[HookConfig] = []
    for entry in data.get("hooks", []):
        cmd = entry.get("command")
        if not isinstance(cmd, list) or not cmd:
            logger.warning("Skipping hook with invalid command: %r", entry)
            continue
        events_raw = entry.get("events", [])
        if not isinstance(events_raw, list):
            events_raw = []
        parsed.append(
            HookConfig(
                command=cmd,
                events=frozenset(events_raw),
            )
        )

    _hooks = parsed
    _loaded = True
    logger.debug("Loaded %d hooks from %s", len(_hooks), hooks_file)
    return _hooks


def _ensure_loaded() -> list[HookConfig]:
    """Lazy-load hooks on first dispatch."""
    if not _loaded:
        load_hooks()
    return _hooks


# ── Payload sanitisation ─────────────────────────────────


def _sanitise_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Truncate ``tool_output`` if present."""
    out = dict(payload)
    if "tool_output" in out and isinstance(out["tool_output"], str):
        if len(out["tool_output"]) > HOOK_TOOL_OUTPUT_LIMIT:
            out["tool_output"] = (
                out["tool_output"][:HOOK_TOOL_OUTPUT_LIMIT] + "…[truncated]"
            )
    return out


# ── Dispatch ─────────────────────────────────────────────


async def _run_hook(hook: HookConfig, event: str, payload: dict[str, Any]) -> None:
    """Run a single hook subprocess, swallowing all errors."""
    env = {**os.environ, "DCODER_HOOK_EVENT": event}
    json_payload = json.dumps(_sanitise_payload(payload))

    try:
        proc = await asyncio.create_subprocess_exec(
            *hook.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=env,
        )
        _, stderr = await asyncio.wait_for(
            proc.communicate(input=json_payload.encode()),
            timeout=HOOK_SUBPROCESS_TIMEOUT,
        )
        if proc.returncode != 0:
            logger.debug(
                "Hook %s exited %d for event %s: %s",
                hook.command[0],
                proc.returncode,
                event,
                stderr.decode(errors="replace")[:200],
            )
    except asyncio.TimeoutError:
        logger.debug(
            "Hook %s timed out after %ds for event %s",
            hook.command[0],
            HOOK_SUBPROCESS_TIMEOUT,
            event,
        )
        with suppress_os_errors():
            proc.kill()  # type: ignore[possibly-undefined]
    except OSError as exc:
        logger.debug("Hook %s failed to start: %s", hook.command[0], exc)


class suppress_os_errors:
    """Context manager that silences OSError (e.g. process already dead)."""

    def __enter__(self) -> None:
        pass

    def __exit__(self, exc_type: type | None, *_: object) -> bool:
        return exc_type is not None and issubclass(exc_type, OSError)


async def dispatch_hook(event: str, payload: dict[str, Any]) -> None:
    """Dispatch *event* to all matching hooks and **await** completion.

    Args:
        event: Event name (e.g. ``"session.start"``).
        payload: JSON-serialisable payload dict.
    """
    hooks = _ensure_loaded()
    tasks = [_run_hook(h, event, payload) for h in hooks if h.matches(event)]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def dispatch_hook_fire_and_forget(event: str, payload: dict[str, Any]) -> None:
    """Dispatch *event* without waiting (for tool events).

    The spawned tasks are tracked internally so ``drain_pending_hooks``
    can await them before session shutdown.

    Args:
        event: Event name.
        payload: JSON-serialisable payload dict.
    """
    hooks = _ensure_loaded()
    matching = [h for h in hooks if h.matches(event)]
    if not matching:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No event loop — fall back to synchronous (shouldn't happen in practice)
        logger.debug("No running loop for fire-and-forget hook dispatch")
        return

    for hook in matching:
        task = loop.create_task(_run_hook(hook, event, payload))
        _pending_tasks.add(task)
        task.add_done_callback(_pending_tasks.discard)


async def drain_pending_hooks() -> None:
    """Wait for all fire-and-forget hooks to complete."""
    if _pending_tasks:
        await asyncio.gather(*_pending_tasks, return_exceptions=True)
        _pending_tasks.clear()
