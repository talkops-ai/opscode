"""Unified approval-mode resolution chain.

Provides a single ``_approval_mode_source()`` function that handles both
``CLIContextSchema`` dataclasses and plain ``dict`` contexts consistently,
producing either a ``_DecidedMode`` (context-only, no store needed) or a
``_LiveLookup`` (validated store key that must be read).

Reference: deepagents_code/agent.py:1780-1889
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dcoder.approval_mode import (
    ApprovalMode,
    approval_mode_key,
    aread_approval_mode_from_store,
    coerce_approval_mode,
    read_approval_mode_from_store,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger("dcoder")

__all__ = [
    "_DecidedMode",
    "_LiveLookup",
    "_approval_mode_source",
    "_aresolve_approval_mode",
    "_resolve_approval_mode",
]


@dataclass(frozen=True)
class _DecidedMode:
    """Context-only approval decision — no store lookup required."""

    mode: ApprovalMode


@dataclass(frozen=True)
class _LiveLookup:
    """A trusted Store key whose record must be read, failing closed to Manual."""

    key: str


def _validated_live_approval_key(
    raw_key: str,
    thread_id: object,
) -> str | None:
    """Validate that *raw_key* matches the canonical key for *thread_id*.

    Returns the key on success, ``None`` on mismatch.
    """
    if not isinstance(thread_id, str) or not thread_id:
        logger.warning(
            "Thread ID missing or invalid for approval-mode key validation"
        )
        return None
    expected = approval_mode_key(thread_id)
    if raw_key != expected:
        logger.warning(
            "Approval-mode key %r does not match expected key for thread %r",
            raw_key,
            thread_id,
        )
        return None
    return raw_key


def _approval_mode_source(context: object) -> _DecidedMode | _LiveLookup:
    """Resolve the live Store lookup or a safe context-only decision.

    Handles both ``CLIContextSchema`` (dataclass) and plain ``dict`` contexts
    consistently.  Returns a ``_LiveLookup`` when a validated store key is
    present, or a ``_DecidedMode`` for context-only resolution.

    Reference: deepagents_code/agent.py:1790-1845
    """
    # Import here to avoid circular imports at module load time.
    from dcoder.agent.factory import CLIContextSchema

    if isinstance(context, CLIContextSchema):
        raw_key: object = context.approval_mode_key
        thread_id: object = context.thread_id
        raw_mode: object = context.approval_mode
        legacy_auto: object = context.auto_approve
        has_typed_mode = True
    elif isinstance(context, dict):
        raw_key = context.get("approval_mode_key")
        thread_id = context.get("thread_id")
        raw_mode = context.get("approval_mode")
        legacy_auto = context.get("auto_approve")
        has_typed_mode = "approval_mode" in context
    else:
        if context is not None:
            logger.warning(
                "approval predicate received unexpected context type %s; "
                "interrupting for safety",
                type(context).__name__,
            )
        return _DecidedMode(ApprovalMode.MANUAL)

    # ── Path 1: Store key present → live lookup ──────────────────
    if raw_key is not None:
        if not isinstance(raw_key, str) or not raw_key:
            logger.warning("Approval-mode Store key is malformed")
            return _DecidedMode(ApprovalMode.MANUAL)
        key = _validated_live_approval_key(raw_key, thread_id)
        if key is None:
            return _DecidedMode(ApprovalMode.MANUAL)
        return _LiveLookup(key)

    # ── Path 2: Typed mode field present ─────────────────────────
    if has_typed_mode and raw_mode:
        requested = coerce_approval_mode(raw_mode)
        if requested is not ApprovalMode.MANUAL:
            # Autonomous mode is present but has no Store key; the TUI might
            # not have written one (e.g. store write failed or agent is local).
            # Trust the typed field directly.
            return _DecidedMode(requested)
        # Compatibility: manual mode with legacy auto_approve=True.
        if raw_mode == ApprovalMode.MANUAL.value and legacy_auto is True:
            return _DecidedMode(ApprovalMode.YOLO)
        return _DecidedMode(ApprovalMode.MANUAL)

    # ── Path 3: Legacy auto_approve only ─────────────────────────
    if legacy_auto is True:
        return _DecidedMode(ApprovalMode.YOLO)
    return _DecidedMode(ApprovalMode.MANUAL)


def _resolve_approval_mode(
    context: object,
    store: object,
) -> ApprovalMode:
    """Resolve approval mode via synchronous local Store interface.

    Reference: deepagents_code/agent.py:1848-1867
    """
    source = _approval_mode_source(context)
    if isinstance(source, _DecidedMode):
        return source.mode
    # _LiveLookup → read from store
    mode = read_approval_mode_from_store(store, source.key)
    if mode is None:
        logger.warning(
            "Approval-mode store item is unavailable; interrupting for safety"
        )
        return ApprovalMode.MANUAL
    return mode


async def _aresolve_approval_mode(
    context: object,
    store: object,
) -> ApprovalMode:
    """Resolve approval mode via async server Store interface.

    Reference: deepagents_code/agent.py:1870-1889
    """
    source = _approval_mode_source(context)
    if isinstance(source, _DecidedMode):
        return source.mode
    # _LiveLookup → read from store
    mode = await aread_approval_mode_from_store(store, source.key)
    if mode is None:
        logger.warning(
            "Approval-mode store item is unavailable; interrupting for safety"
        )
        return ApprovalMode.MANUAL
    return mode
