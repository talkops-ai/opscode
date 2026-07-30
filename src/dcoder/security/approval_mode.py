"""Live approval-mode state shared through the LangGraph Store."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from hashlib import sha256
from typing import TypedDict

logger = logging.getLogger("dcoder")

APPROVAL_MODE_NAMESPACE: tuple[str, str] = ("dcoder", "approval_mode")


class ApprovalModePayload(TypedDict):
    auto_approve: bool


def approval_mode_key(thread_id: str) -> str:
    """Return the store key for a thread's live approval mode."""
    return sha256(thread_id.encode("utf-8")).hexdigest()


def approval_mode_payload(*, auto_approve: bool) -> ApprovalModePayload:
    return {"auto_approve": auto_approve}


def _item_value(item: object) -> object:
    if isinstance(item, Mapping):
        return item.get("value")
    return getattr(item, "value", None)


def read_approval_mode_from_store(store: object, key: str | None) -> bool | None:
    """Read a live approval mode from the server-side LangGraph Store."""
    if store is None:
        logger.debug("Approval-mode store is unavailable")
        return None
    if not isinstance(key, str) or not key:
        logger.debug("Approval-mode store key is missing or invalid")
        return None

    get = getattr(store, "get", None)
    if get is None:
        logger.debug("Approval-mode store does not expose get()")
        return None

    try:
        item = get(APPROVAL_MODE_NAMESPACE, key)
    except Exception:
        logger.warning("Could not read approval-mode store item", exc_info=True)
        return None
    if item is None:
        logger.debug("Approval-mode store item is missing")
        return None

    value = _item_value(item)
    auto_approve = value.get("auto_approve") if isinstance(value, Mapping) else None
    if isinstance(auto_approve, bool):
        return auto_approve

    logger.debug("Approval-mode store item has invalid contents")
    return None


async def awrite_approval_mode(
    agent: object,
    thread_id: str,
    *,
    auto_approve: bool,
) -> str | None:
    """Persist approval mode through an agent's remote store client."""
    put = getattr(agent, "aput_store_item", None)
    if put is None:
        return None

    key = approval_mode_key(thread_id)
    await put(
        APPROVAL_MODE_NAMESPACE,
        key,
        approval_mode_payload(auto_approve=auto_approve),
    )
    return key
