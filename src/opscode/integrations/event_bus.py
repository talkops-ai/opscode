"""Unix-domain-socket event bus for opscode.

Lets external processes push commands, prompts, and signals into a running
agent session over a Unix socket using newline-delimited JSON.

Wire protocol
~~~~~~~~~~~~~

**Request** (one JSON object per line)::

    {"kind": "prompt", "payload": "Deploy to staging", "source": "ci-pipeline"}
    {"kind": "signal", "payload": "interrupt", "source": "watchdog"}
    {"kind": "command", "payload": "/compact", "source": "automation"}

**Response**::

    {"ok": true}
    {"ok": false, "error": "invalid kind: foobar"}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

# ── Types ────────────────────────────────────────────────

ExternalEventKind = Literal["command", "prompt", "signal"]
ExternalSignal = Literal["interrupt", "force-clear"]

_VALID_KINDS: frozenset[str] = frozenset({"command", "prompt", "signal"})
_VALID_SIGNALS: frozenset[str] = frozenset({"interrupt", "force-clear"})


class BypassTier(IntEnum):
    """Priority tier for incoming events."""

    QUEUED = 0
    """Normal — enters the async queue."""

    IMMEDIATE = 1
    """Skip the queue and deliver directly (reserved for signals)."""


@dataclass(frozen=True)
class ExternalEvent:
    """A validated event received over the Unix socket."""

    kind: ExternalEventKind
    """``"command"``, ``"prompt"``, or ``"signal"``."""

    payload: str
    """The event content (prompt text, command string, or signal name)."""

    source: str
    """Identifier of the sending process / system."""

    bypass: BypassTier = BypassTier.QUEUED
    """Delivery priority."""

    correlation_id: str | None = None
    """Optional caller-provided correlation ID for request tracking."""


# ── EventBus ─────────────────────────────────────────────

_MAX_LINE_LENGTH = 64 * 1024  # 64 KiB per JSON line


class EventBus:
    """Async Unix-domain-socket server that receives ``ExternalEvent`` objects.

    Usage::

        bus = EventBus()
        await bus.start("/tmp/opscode.sock")
        try:
            while True:
                event = await bus.get_event()
                print(event)
        finally:
            await bus.stop()
    """

    def __init__(self, queue_size: int = 256) -> None:
        self._queue: asyncio.Queue[ExternalEvent] = asyncio.Queue(maxsize=queue_size)
        self._server: asyncio.Server | None = None
        self._socket_path: Path | None = None

    # ── Lifecycle ────────────────────────────────────────

    async def start(self, socket_path: str | Path) -> None:
        """Bind the Unix socket and start accepting connections.

        Args:
            socket_path: Filesystem path for the Unix-domain socket.
                         Existing sockets at this path are unlinked first.
        """
        path = Path(socket_path)

        # Clean up stale socket
        if path.exists():
            try:
                path.unlink()
            except OSError:
                logger.warning("Could not remove stale socket %s", path)

        path.parent.mkdir(parents=True, exist_ok=True)

        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(path),
        )
        self._socket_path = path

        # Restrict socket permissions to owner only
        try:
            os.chmod(str(path), 0o600)
        except OSError:
            logger.debug("Could not set socket permissions on %s", path)

        logger.info("Event bus listening on %s", path)

    async def stop(self) -> None:
        """Shut down the server and remove the socket file."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        if self._socket_path is not None and self._socket_path.exists():
            try:
                self._socket_path.unlink()
            except OSError:
                logger.debug("Could not remove socket %s", self._socket_path)
            self._socket_path = None

    @property
    def running(self) -> bool:
        """Whether the server is currently accepting connections."""
        return self._server is not None and self._server.is_serving()

    # ── Consumer API ─────────────────────────────────────

    async def get_event(self) -> ExternalEvent:
        """Block until an event is available and return it."""
        return await self._queue.get()

    def get_event_nowait(self) -> ExternalEvent | None:
        """Return the next event or ``None`` if the queue is empty."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    # ── Connection handler ───────────────────────────────

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Process one client connection (may send multiple newline-delimited events)."""
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break  # EOF

                if len(line) > _MAX_LINE_LENGTH:
                    await self._send_response(
                        writer, ok=False, error="payload too large"
                    )
                    continue

                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue

                try:
                    data = json.loads(text)
                except json.JSONDecodeError as exc:
                    await self._send_response(
                        writer, ok=False, error=f"invalid JSON: {exc}"
                    )
                    continue

                event, error = self._validate_event(data)
                if error is not None:
                    await self._send_response(writer, ok=False, error=error)
                    continue

                assert event is not None
                try:
                    self._queue.put_nowait(event)
                except asyncio.QueueFull:
                    await self._send_response(
                        writer, ok=False, error="event queue full"
                    )
                    continue

                await self._send_response(writer, ok=True)
        except (ConnectionError, OSError):
            pass  # Client disconnected
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass

    # ── Validation ───────────────────────────────────────

    @staticmethod
    def _validate_event(
        data: dict[str, object],
    ) -> tuple[ExternalEvent | None, str | None]:
        """Parse and validate a raw JSON dict into an ``ExternalEvent``.

        Returns:
            ``(event, None)`` on success, ``(None, error_message)`` on failure.
        """
        if not isinstance(data, dict):
            return None, "expected JSON object"

        kind = data.get("kind")
        if kind not in _VALID_KINDS:
            return None, f"invalid kind: {kind!r} (expected one of {sorted(_VALID_KINDS)})"

        payload = data.get("payload", "")
        if not isinstance(payload, str) or not payload.strip():
            return None, "payload must be a non-empty string"

        source = data.get("source", "unknown")
        if not isinstance(source, str):
            source = "unknown"

        # Validate signals
        if kind == "signal" and payload not in _VALID_SIGNALS:
            return None, (
                f"invalid signal: {payload!r} "
                f"(expected one of {sorted(_VALID_SIGNALS)})"
            )

        bypass = BypassTier.IMMEDIATE if kind == "signal" else BypassTier.QUEUED
        correlation_id = data.get("correlation_id")
        if correlation_id is not None and not isinstance(correlation_id, str):
            correlation_id = None

        return (
            ExternalEvent(
                kind=kind,  # type: ignore[arg-type]
                payload=payload,
                source=source,
                bypass=bypass,
                correlation_id=correlation_id,
            ),
            None,
        )

    # ── Helpers ──────────────────────────────────────────

    @staticmethod
    async def _send_response(
        writer: asyncio.StreamWriter,
        *,
        ok: bool,
        error: str | None = None,
    ) -> None:
        """Send a JSON response line to the client."""
        resp: dict[str, object] = {"ok": ok}
        if error is not None:
            resp["error"] = error
        try:
            writer.write(json.dumps(resp).encode() + b"\n")
            await writer.drain()
        except (ConnectionError, OSError):
            pass
