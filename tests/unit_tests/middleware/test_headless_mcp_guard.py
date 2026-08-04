import pytest
from unittest.mock import MagicMock
from langchain_core.messages import ToolMessage
from langchain.agents.middleware.types import ToolCallRequest
from dcoder.security.approval_mode import ApprovalMode, coerce_approval_mode, approval_mode_payload
from dcoder.middleware.headless_mcp_guard import (
    HeadlessMCPGuardMiddleware,
    gated_mcp_tool_names,
    mcp_tool_is_coherently_read_only,
)


def test_approval_mode_coercion():
    assert coerce_approval_mode("manual") == ApprovalMode.MANUAL
    assert coerce_approval_mode("auto") == ApprovalMode.AUTO
    assert coerce_approval_mode("yolo") == ApprovalMode.YOLO
    assert coerce_approval_mode("invalid") == ApprovalMode.MANUAL
    assert coerce_approval_mode(True) == ApprovalMode.YOLO
    assert coerce_approval_mode(False) == ApprovalMode.MANUAL


def test_approval_mode_payload():
    payload = approval_mode_payload(mode=ApprovalMode.AUTO)
    assert payload["mode"] == "auto"
    assert payload.get("auto_approve") is False

    payload_yolo = approval_mode_payload(auto_approve=True)
    assert payload_yolo["mode"] == "yolo"
    assert payload_yolo.get("auto_approve") is True


def test_mcp_read_only_hint_detection():
    ro_tool = MagicMock()
    ro_tool.name = "get_pods"
    ro_tool.metadata = {"readOnlyHint": True}

    mutating_tool = MagicMock()
    mutating_tool.name = "delete_pod"
    mutating_tool.metadata = {"readOnlyHint": False}

    unannotated_tool = MagicMock()
    unannotated_tool.name = "unknown_tool"
    unannotated_tool.metadata = None

    destructive_tool = MagicMock()
    destructive_tool.name = "destroy"
    destructive_tool.metadata = {"readOnlyHint": True, "destructiveHint": True}

    assert mcp_tool_is_coherently_read_only(ro_tool) is True
    assert mcp_tool_is_coherently_read_only(mutating_tool) is False
    assert mcp_tool_is_coherently_read_only(unannotated_tool) is False
    assert mcp_tool_is_coherently_read_only(destructive_tool) is False

    gated = gated_mcp_tool_names([ro_tool, mutating_tool, unannotated_tool, destructive_tool])
    assert gated == {"delete_pod", "unknown_tool", "destroy"}


def test_headless_mcp_guard_middleware_blocks_gated():
    guard = HeadlessMCPGuardMiddleware(tool_names={"delete_pod", "destroy"})

    from typing import cast, Any
    allowed_req = ToolCallRequest(
        tool_call={"name": "get_pods", "args": {}, "id": "1"},
        tool=cast(Any, MagicMock()),
        state={},
        runtime=cast(Any, MagicMock()),
    )
    blocked_req = ToolCallRequest(
        tool_call={"name": "delete_pod", "args": {}, "id": "2"},
        tool=cast(Any, MagicMock()),
        state={},
        runtime=cast(Any, MagicMock()),
    )

    handler = MagicMock(return_value="OK")

    res_allowed = guard.wrap_tool_call(allowed_req, handler)
    assert res_allowed == "OK"

    res_blocked = guard.wrap_tool_call(blocked_req, handler)
    assert isinstance(res_blocked, ToolMessage)
    assert res_blocked.status == "error"
    assert "headless runtime has no approval UI" in res_blocked.content
