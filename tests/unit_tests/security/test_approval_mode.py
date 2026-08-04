"""Unit tests for approval_mode — coercion, payload construction, modes."""

import pytest

from dcoder.security.approval_mode import (
    ApprovalMode,
    approval_mode_payload,
    coerce_approval_mode,
)


class TestCoerceApprovalMode:
    """Tests for coerce_approval_mode."""

    def test_string_values(self):
        assert coerce_approval_mode("manual") == ApprovalMode.MANUAL
        assert coerce_approval_mode("auto") == ApprovalMode.AUTO
        assert coerce_approval_mode("yolo") == ApprovalMode.YOLO

    def test_case_insensitive(self):
        assert coerce_approval_mode("MANUAL") == ApprovalMode.MANUAL
        assert coerce_approval_mode("Auto") == ApprovalMode.AUTO
        assert coerce_approval_mode("YOLO") == ApprovalMode.YOLO

    def test_boolean_values(self):
        assert coerce_approval_mode(True) == ApprovalMode.YOLO
        assert coerce_approval_mode(False) == ApprovalMode.MANUAL

    def test_invalid_defaults_to_manual(self):
        assert coerce_approval_mode("invalid") == ApprovalMode.MANUAL
        assert coerce_approval_mode("") == ApprovalMode.MANUAL
        assert coerce_approval_mode(None) == ApprovalMode.MANUAL
        assert coerce_approval_mode(42) == ApprovalMode.MANUAL

    def test_approval_mode_enum_values(self):
        assert coerce_approval_mode(ApprovalMode.AUTO) == ApprovalMode.AUTO


class TestApprovalModePayload:
    def test_auto_mode(self):
        payload = approval_mode_payload(mode=ApprovalMode.AUTO)
        assert payload["mode"] == "auto"
        assert payload.get("auto_approve") is False

    def test_yolo_mode(self):
        payload = approval_mode_payload(mode=ApprovalMode.YOLO)
        assert payload["mode"] == "yolo"
        assert payload.get("auto_approve") is True

    def test_manual_mode(self):
        payload = approval_mode_payload(mode=ApprovalMode.MANUAL)
        assert payload["mode"] == "manual"
        assert payload.get("auto_approve") is False

    def test_auto_approve_flag(self):
        payload = approval_mode_payload(auto_approve=True)
        assert payload["mode"] == "yolo"
        assert payload.get("auto_approve") is True

        payload = approval_mode_payload(auto_approve=False)
        assert payload["mode"] == "manual"
        assert payload.get("auto_approve") is False
