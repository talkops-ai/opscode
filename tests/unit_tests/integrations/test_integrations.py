"""Tests for the dcoder.integrations package (hooks, event_bus, notifications)."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest

from dcoder.integrations.hooks import (
    HOOK_TOOL_OUTPUT_LIMIT,
    HookConfig,
    _sanitise_payload,
    dispatch_hook,
    load_hooks,
)
from dcoder.integrations.event_bus import EventBus, ExternalEvent, _VALID_KINDS


# ── Hooks ────────────────────────────────────────────────


class TestHookConfig:
    def test_matches_all_events_when_empty(self):
        hook = HookConfig(command=["echo"], events=frozenset())
        assert hook.matches("session.start")
        assert hook.matches("any.event")

    def test_matches_only_listed_events(self):
        hook = HookConfig(
            command=["echo"],
            events=frozenset({"session.start", "task.complete"}),
        )
        assert hook.matches("session.start")
        assert hook.matches("task.complete")
        assert not hook.matches("session.end")


class TestLoadHooks:
    def test_loads_valid_config(self, tmp_path: Path):
        config = {
            "hooks": [
                {"command": ["bash", "notify.sh"], "events": ["session.start"]},
                {"command": ["python", "audit.py"], "events": []},
            ]
        }
        hooks_file = tmp_path / "hooks.json"
        hooks_file.write_text(json.dumps(config))

        hooks = load_hooks(hooks_file)
        assert len(hooks) == 2
        assert hooks[0].command == ["bash", "notify.sh"]
        assert hooks[0].events == frozenset({"session.start"})
        assert hooks[1].events == frozenset()

    def test_returns_empty_for_missing_file(self, tmp_path: Path):
        hooks = load_hooks(tmp_path / "nonexistent.json")
        assert hooks == []

    def test_skips_hooks_with_invalid_command(self, tmp_path: Path):
        config = {
            "hooks": [
                {"command": "not-a-list", "events": []},
                {"command": [], "events": []},
                {"command": ["valid"], "events": []},
            ]
        }
        hooks_file = tmp_path / "hooks.json"
        hooks_file.write_text(json.dumps(config))

        hooks = load_hooks(hooks_file)
        assert len(hooks) == 1
        assert hooks[0].command == ["valid"]

    def test_handles_malformed_json(self, tmp_path: Path):
        hooks_file = tmp_path / "hooks.json"
        hooks_file.write_text("{invalid json")

        hooks = load_hooks(hooks_file)
        assert hooks == []


class TestPayloadSanitisation:
    def test_truncates_tool_output(self):
        payload = {"tool_output": "x" * 5000}
        result = _sanitise_payload(payload)
        assert len(result["tool_output"]) <= HOOK_TOOL_OUTPUT_LIMIT + 20  # + truncation marker

    def test_preserves_short_output(self):
        payload = {"tool_output": "short"}
        result = _sanitise_payload(payload)
        assert result["tool_output"] == "short"

    def test_preserves_non_output_fields(self):
        payload = {"tool_name": "execute", "tool_args": {"cmd": "ls"}}
        result = _sanitise_payload(payload)
        assert result == payload


@pytest.mark.asyncio
async def test_dispatch_hook_with_no_hooks(tmp_path: Path):
    """dispatch_hook should be a no-op when no hooks are configured."""
    load_hooks(tmp_path / "nonexistent.json")
    # Should not raise
    await dispatch_hook("session.start", {"session_id": "test"})


# ── Event Bus ────────────────────────────────────────────


class TestEventBusValidation:
    def test_validates_valid_prompt_event(self):
        data = {"kind": "prompt", "payload": "Deploy to staging", "source": "ci"}
        event, error = EventBus._validate_event(cast(dict[str, Any], data))
        assert error is None
        assert event is not None
        assert event.kind == "prompt"
        assert event.payload == "Deploy to staging"
        assert event.source == "ci"

    def test_validates_valid_signal_event(self):
        data = {"kind": "signal", "payload": "interrupt", "source": "watchdog"}
        event, error = EventBus._validate_event(cast(dict[str, Any], data))
        assert error is None
        assert event is not None
        assert event.kind == "signal"

    def test_rejects_invalid_kind(self):
        data = {"kind": "invalid", "payload": "test", "source": "test"}
        event, error = EventBus._validate_event(cast(dict[str, Any], data))
        assert event is None
        assert error is not None and "invalid kind" in error

    def test_rejects_empty_payload(self):
        data = {"kind": "prompt", "payload": "", "source": "test"}
        event, error = EventBus._validate_event(cast(dict[str, Any], data))
        assert event is None
        assert error is not None and "non-empty" in error

    def test_rejects_invalid_signal(self):
        data = {"kind": "signal", "payload": "unknown-signal", "source": "test"}
        event, error = EventBus._validate_event(cast(dict[str, Any], data))
        assert event is None
        assert error is not None and "invalid signal" in error

    def test_rejects_non_dict(self):
        event, error = EventBus._validate_event("not a dict")  # type: ignore[arg-type]
        assert event is None
        assert error is not None and "expected JSON object" in error

    def test_preserves_correlation_id(self):
        data = {
            "kind": "prompt",
            "payload": "test",
            "source": "ci",
            "correlation_id": "req-123",
        }
        event, error = EventBus._validate_event(cast(dict[str, Any], data))
        assert error is None
        assert event is not None
        assert event.correlation_id == "req-123"


@pytest.mark.asyncio
async def test_event_bus_lifecycle(tmp_path: Path):
    """Start, send an event, receive it, and stop."""
    # macOS limits AF_UNIX paths to 104 bytes — use /tmp with short name
    import uuid

    socket_path = Path(f"/tmp/dctest_{uuid.uuid4().hex[:8]}.sock")
    bus = EventBus()
    try:
        await bus.start(socket_path)
        assert bus.running

        # Connect and send an event
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        event_data = json.dumps(
            {"kind": "prompt", "payload": "hello", "source": "test"}
        )
        writer.write(event_data.encode() + b"\n")
        await writer.drain()

        # Read response
        response_line = await asyncio.wait_for(reader.readline(), timeout=2)
        response = json.loads(response_line)
        assert response["ok"] is True

        # Receive the event
        event = await asyncio.wait_for(bus.get_event(), timeout=2)
        assert event.kind == "prompt"
        assert event.payload == "hello"

        writer.close()
        await writer.wait_closed()
    finally:
        await bus.stop()
        if socket_path.exists():
            socket_path.unlink()
    assert not bus.running


@pytest.mark.asyncio
async def test_event_bus_rejects_invalid_json(tmp_path: Path):
    """Invalid JSON should return an error response."""
    import uuid

    socket_path = Path(f"/tmp/dctest_{uuid.uuid4().hex[:8]}.sock")
    bus = EventBus()
    try:
        await bus.start(socket_path)

        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b"{bad json}\n")
        await writer.drain()

        response_line = await asyncio.wait_for(reader.readline(), timeout=2)
        response = json.loads(response_line)
        assert response["ok"] is False
        assert "invalid JSON" in response["error"]

        writer.close()
        await writer.wait_closed()
    finally:
        await bus.stop()
        if socket_path.exists():
            socket_path.unlink()


# ── Notifications ────────────────────────────────────────


@pytest.mark.asyncio
async def test_notify_session_start():
    """notify_session_start should dispatch session.start event."""
    from dcoder.integrations.notifications import notify_session_start

    with patch("dcoder.integrations.notifications.dispatch_hook", new_callable=AsyncMock) as mock:
        await notify_session_start("sess-1", "gpt-4o")
        mock.assert_called_once_with(
            "session.start",
            {"session_id": "sess-1", "model": "gpt-4o"},
        )


@pytest.mark.asyncio
async def test_notify_task_complete():
    """notify_task_complete should dispatch task.complete event."""
    from dcoder.integrations.notifications import notify_task_complete

    with patch("dcoder.integrations.notifications.dispatch_hook", new_callable=AsyncMock) as mock:
        await notify_task_complete("Deployment finished")
        mock.assert_called_once_with(
            "task.complete",
            {"summary": "Deployment finished"},
        )
