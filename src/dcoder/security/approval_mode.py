"""Re-export approval-mode state from dcoder.approval_mode for backwards compatibility."""

from __future__ import annotations

from dcoder.approval_mode import (
    APPROVAL_MODE_NAMESPACE,
    ApprovalMode,
    ApprovalModePayload,
    approval_mode_key,
    approval_mode_payload,
    aread_approval_mode_from_store,
    awrite_approval_mode,
    coerce_approval_mode,
    has_auto_mode_notice,
    has_yolo_acknowledgement,
    next_approval_mode,
    read_approval_mode_from_store,
    save_auto_mode_notice,
    save_yolo_acknowledgement,
    yolo_acknowledgement_path,
)

__all__ = [
    "APPROVAL_MODE_NAMESPACE",
    "ApprovalMode",
    "ApprovalModePayload",
    "approval_mode_key",
    "approval_mode_payload",
    "aread_approval_mode_from_store",
    "awrite_approval_mode",
    "coerce_approval_mode",
    "has_auto_mode_notice",
    "has_yolo_acknowledgement",
    "next_approval_mode",
    "read_approval_mode_from_store",
    "save_auto_mode_notice",
    "save_yolo_acknowledgement",
    "yolo_acknowledgement_path",
]
