"""Unit tests for ApprovalMode enum, precedence, Shift+Tab cycle, and persistence."""

from __future__ import annotations

from pathlib import Path
import pytest

from dcoder.approval_mode import (
    ApprovalMode,
    approval_mode_key,
    approval_mode_payload,
    coerce_approval_mode,
    has_auto_mode_notice,
    has_yolo_acknowledgement,
    next_approval_mode,
    save_auto_mode_notice,
    save_yolo_acknowledgement,
)


def test_coerce_approval_mode():
    assert coerce_approval_mode("manual") == ApprovalMode.MANUAL
    assert coerce_approval_mode("auto") == ApprovalMode.AUTO
    assert coerce_approval_mode("yolo") == ApprovalMode.YOLO
    assert coerce_approval_mode("invalid_mode") == ApprovalMode.MANUAL
    assert coerce_approval_mode(None) == ApprovalMode.MANUAL
    assert coerce_approval_mode(123) == ApprovalMode.MANUAL


def test_next_approval_mode_full_cycle():
    # Manual -> Auto -> YOLO -> Manual
    mode = next_approval_mode(
        ApprovalMode.MANUAL, auto_eligible=True, yolo_switcher_enabled=True
    )
    assert mode == ApprovalMode.AUTO

    mode = next_approval_mode(
        ApprovalMode.AUTO, auto_eligible=True, yolo_switcher_enabled=True
    )
    assert mode == ApprovalMode.YOLO

    mode = next_approval_mode(
        ApprovalMode.YOLO, auto_eligible=True, yolo_switcher_enabled=True
    )
    assert mode == ApprovalMode.MANUAL


def test_next_approval_mode_sandbox_ineligible():
    # Auto omitted when auto_eligible=False: Manual -> YOLO -> Manual
    mode = next_approval_mode(
        ApprovalMode.MANUAL, auto_eligible=False, yolo_switcher_enabled=True
    )
    assert mode == ApprovalMode.YOLO

    mode = next_approval_mode(
        ApprovalMode.YOLO, auto_eligible=False, yolo_switcher_enabled=True
    )
    assert mode == ApprovalMode.MANUAL


def test_next_approval_mode_yolo_disabled():
    # YOLO omitted when yolo_switcher_enabled=False: Manual -> Auto -> Manual
    mode = next_approval_mode(
        ApprovalMode.MANUAL, auto_eligible=True, yolo_switcher_enabled=False
    )
    assert mode == ApprovalMode.AUTO

    mode = next_approval_mode(
        ApprovalMode.AUTO, auto_eligible=True, yolo_switcher_enabled=False
    )
    assert mode == ApprovalMode.MANUAL


def test_approval_mode_key():
    key1 = approval_mode_key("thread-123")
    key2 = approval_mode_key("thread-123")
    key3 = approval_mode_key("thread-456")
    assert key1 == key2
    assert key1 != key3
    assert len(key1) == 64  # SHA256 hex digest length


def test_approval_mode_payload():
    payload = approval_mode_payload(mode=ApprovalMode.AUTO)
    assert payload == {"mode": "auto"}

    payload_bool = approval_mode_payload(auto_approve=True)
    assert payload_bool == {"mode": "yolo"}

    with pytest.raises(ValueError):
        approval_mode_payload()

    with pytest.raises(ValueError):
        approval_mode_payload(mode=ApprovalMode.AUTO, auto_approve=True)


def test_yolo_and_auto_notice_persistence(tmp_path: Path):
    target = tmp_path / "approval.json"

    assert not has_yolo_acknowledgement(target)
    assert not has_auto_mode_notice(target)

    # Save YOLO acknowledgement
    assert save_yolo_acknowledgement(target)
    assert has_yolo_acknowledgement(target)
    assert not has_auto_mode_notice(target)

    # Save Auto notice (merging without clobbering YOLO acknowledgement)
    assert save_auto_mode_notice(target)
    assert has_yolo_acknowledgement(target)
    assert has_auto_mode_notice(target)


@pytest.mark.asyncio
async def test_store_read_write_approval_mode():
    from dcoder.approval_mode import (
        aread_approval_mode_from_store,
        awrite_approval_mode,
        read_approval_mode_from_store,
    )

    store_data: dict[tuple[str, str], dict] = {}

    class MockAgent:
        async def aput_store_item(self, ns: tuple[str, str], key: str, value: dict):
            store_data[(ns[0], key)] = {"value": value}

    class MockStore:
        def get(self, ns: tuple[str, str], key: str):
            return store_data.get((ns[0], key))

        async def aget(self, ns: tuple[str, str], key: str):
            return store_data.get((ns[0], key))

    agent = MockAgent()
    store = MockStore()

    thread_id = "test-thread-999"
    key = await awrite_approval_mode(agent, thread_id, mode=ApprovalMode.AUTO)
    assert key == approval_mode_key(thread_id)

    read_sync = read_approval_mode_from_store(store, key)
    assert read_sync == ApprovalMode.AUTO

    read_async = await aread_approval_mode_from_store(store, key)
    assert read_async == ApprovalMode.AUTO
