"""Unified approval-mode resolution and security policy evaluation.

Provides ``ApprovalPolicyResolver`` and convenience functions (``_approval_mode_source``,
``_resolve_approval_mode``, ``_aresolve_approval_mode``) for resolving runtime execution
permissions across dataclass and dictionary contexts.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from opscode.approval_mode import (
    ApprovalMode,
    approval_mode_key,
    aread_approval_mode_from_store,
    coerce_approval_mode,
    read_approval_mode_from_store,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger("opscode")

__all__ = [
    "ApprovalPolicyResolver",
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


class ApprovalPolicyResolver:
    """Evaluates execution context to determine active approval constraints."""

    @staticmethod
    def validate_store_key(raw_key: str, thread_id: object) -> str | None:
        """Validate that *raw_key* matches the canonical key for *thread_id*.

        Returns the key on success, ``None`` on mismatch or invalid input.
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

    @classmethod
    def resolve_source(cls, context: object) -> _DecidedMode | _LiveLookup:
        """Extract approval mode from invocation context (dataclass or dict)."""
        from opscode.agent.factory import CLIContextSchema

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

        # 1. Store key present -> live store lookup
        if raw_key is not None:
            if not isinstance(raw_key, str) or not raw_key:
                logger.warning("Approval-mode Store key is malformed")
                return _DecidedMode(ApprovalMode.MANUAL)
            key = cls.validate_store_key(raw_key, thread_id)
            if key is None:
                return _DecidedMode(ApprovalMode.MANUAL)
            return _LiveLookup(key)

        # 2. Explicit typed mode present
        if has_typed_mode and raw_mode:
            requested = coerce_approval_mode(raw_mode)
            if requested is not ApprovalMode.MANUAL:
                return _DecidedMode(requested)
            if raw_mode == ApprovalMode.MANUAL.value and legacy_auto is True:
                return _DecidedMode(ApprovalMode.YOLO)
            return _DecidedMode(ApprovalMode.MANUAL)

        # 3. Legacy auto_approve flag fallback
        if legacy_auto is True:
            return _DecidedMode(ApprovalMode.YOLO)
        return _DecidedMode(ApprovalMode.MANUAL)

    @classmethod
    def resolve_sync(cls, context: object, store: object) -> ApprovalMode:
        """Resolve approval mode synchronously using local store."""
        source = cls.resolve_source(context)
        if isinstance(source, _DecidedMode):
            return source.mode
        mode = read_approval_mode_from_store(store, source.key)
        if mode is None:
            logger.warning(
                "Approval-mode store item is unavailable; interrupting for safety"
            )
            return ApprovalMode.MANUAL
        return mode

    @classmethod
    async def resolve_async(cls, context: object, store: object) -> ApprovalMode:
        """Resolve approval mode asynchronously using server store."""
        source = cls.resolve_source(context)
        if isinstance(source, _DecidedMode):
            return source.mode
        mode = await aread_approval_mode_from_store(store, source.key)
        if mode is None:
            logger.warning(
                "Approval-mode store item is unavailable; interrupting for safety"
            )
            return ApprovalMode.MANUAL
        return mode


def _validated_live_approval_key(raw_key: str, thread_id: object) -> str | None:
    return ApprovalPolicyResolver.validate_store_key(raw_key, thread_id)


def _approval_mode_source(context: object) -> _DecidedMode | _LiveLookup:
    return ApprovalPolicyResolver.resolve_source(context)


def _resolve_approval_mode(context: object, store: object) -> ApprovalMode:
    return ApprovalPolicyResolver.resolve_sync(context, store)


async def _aresolve_approval_mode(context: object, store: object) -> ApprovalMode:
    return await ApprovalPolicyResolver.resolve_async(context, store)
