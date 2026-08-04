"""Approval-mode state shared by the client and agent server."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from enum import Enum
from hashlib import sha256
from typing import NotRequired, TypedDict

logger = logging.getLogger("dcoder")

APPROVAL_MODE_NAMESPACE: tuple[str, str] = ("dcoder", "approval_mode")


class ApprovalMode(str, Enum):
    """Tool-approval policy selected for an interactive thread."""

    MANUAL = "manual"
    AUTO = "auto"
    YOLO = "yolo"


class ApprovalModePayload(TypedDict):
    """Stored approval-mode control payload."""

    mode: str
    auto_approve: NotRequired[bool]


def coerce_approval_mode(value: object) -> ApprovalMode:
    """Return a validated mode, failing closed to `manual`."""
    if isinstance(value, ApprovalMode):
        return value
    if isinstance(value, str):
        try:
            return ApprovalMode(value.lower())
        except ValueError:
            pass
    if isinstance(value, bool):
        return ApprovalMode.YOLO if value else ApprovalMode.MANUAL
    return ApprovalMode.MANUAL


def approval_mode_key(thread_id: str) -> str:
    """Return the store key for a thread's live approval mode."""
    return sha256(thread_id.encode("utf-8")).hexdigest()


def approval_mode_payload(
    *,
    mode: ApprovalMode | str | None = None,
    auto_approve: bool | None = None,
) -> ApprovalModePayload:
    """Return the stored approval-mode payload supporting mode and legacy auto_approve."""
    if mode is not None:
        resolved = coerce_approval_mode(mode)
    elif auto_approve is not None:
        resolved = ApprovalMode.YOLO if auto_approve else ApprovalMode.MANUAL
    else:
        resolved = ApprovalMode.MANUAL

    return {
        "mode": resolved.value,
        "auto_approve": resolved == ApprovalMode.YOLO,
    }


def _item_value(item: object) -> object:
    if isinstance(item, Mapping):
        return item.get("value")
    return getattr(item, "value", None)


def read_approval_mode_from_store(store: object, key: str | None) -> ApprovalMode | None:
    """Read a live approval mode from the server-side LangGraph Store."""
    if store is None or not isinstance(key, str) or not key:
        return None

    get = getattr(store, "get", None)
    if get is None:
        return None

    try:
        item = get(APPROVAL_MODE_NAMESPACE, key)
    except Exception:
        logger.warning("Could not read approval-mode store item", exc_info=True)
        return None
    if item is None:
        return None

    value = _item_value(item)
    if isinstance(value, Mapping):
        mode_val = value.get("mode")
        if isinstance(mode_val, str):
            return coerce_approval_mode(mode_val)
        auto_app = value.get("auto_approve")
        if isinstance(auto_app, bool):
            return ApprovalMode.YOLO if auto_app else ApprovalMode.MANUAL

    return None


async def awrite_approval_mode(
    agent: object,
    thread_id: str,
    *,
    mode: ApprovalMode | str | None = None,
    auto_approve: bool | None = None,
) -> str | None:
    """Persist approval mode through an agent's remote store client."""
    put = getattr(agent, "aput_store_item", None)
    if put is None:
        return None

    key = approval_mode_key(thread_id)
    await put(
        APPROVAL_MODE_NAMESPACE,
        key,
        approval_mode_payload(mode=mode, auto_approve=auto_approve),
    )
    return key
