"""Comprehensive unit tests for ServerHooksMiddleware, hook events, and transport."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from dcoder.hooks.interrupt import (
    build_hook_interrupt_payload,
    build_hook_resume_value,
    parse_hook_interrupt_payload,
    parse_hook_resume_value,
)
from dcoder.hooks.models.domain import (
    AgentIdentity,
    CompactTrigger,
    HookContext,
    HookEvent,
    HookInvocation,
    PermissionEffect,
    PostToolUseDecision,
    PostToolUseEvent,
    PreCompactDecision,
    PreCompactEvent,
    PreToolUseDecision,
    PreToolUseEvent,
    StopDecision,
    StopEvent,
    SubagentStartDecision,
    SubagentStartEvent,
    SubagentStopDecision,
    SubagentStopEvent,
    ToolCallData,
)
from dcoder.hooks.models.transport import HookInvocationRequest, HookInvocationResponse
from dcoder.hooks.tools import format_mcp_wire_name, to_wire_call, to_wire_tool_name
from dcoder.middleware.server_hooks import (
    ServerHooksMiddleware,
    ServerHooksState,
    hook_decided_permission,
)
from dcoder.security.approval_mode import ApprovalMode


# ---------------------------------------------------------------------------
# 1. ServerHooksMiddleware Lifecycle & Instantiation
# ---------------------------------------------------------------------------

def test_server_hooks_middleware_instantiation() -> None:
    middleware = ServerHooksMiddleware(cwd=Path("/tmp"), emit_stop=True)
    assert middleware._cwd == Path("/tmp")
    assert middleware._emit_stop is True
    assert middleware.state_schema == ServerHooksState


def test_server_hooks_after_model_no_gate() -> None:
    middleware = ServerHooksMiddleware(cwd=Path("/tmp"))
    runtime = MagicMock()
    runtime.context = None

    state: ServerHooksState = {"messages": []}
    result = middleware.after_model(state, runtime)
    assert result == {"_hooks_pre_tool_outcomes": {}}


def test_server_hooks_after_agent_no_gate() -> None:
    middleware = ServerHooksMiddleware(cwd=Path("/tmp"))
    runtime = MagicMock()
    runtime.context = None

    state: ServerHooksState = {"messages": []}
    result = middleware.after_agent(state, runtime)
    assert result is None


def test_server_hooks_after_agent_emit_stop_disabled() -> None:
    middleware = ServerHooksMiddleware(cwd=Path("/tmp"), emit_stop=False)
    runtime = MagicMock()
    runtime.context = {
        "hooks_snapshot_id": "snap-123",
        "hooks_server_events": [HookEvent.STOP.value],
    }

    state: ServerHooksState = {"messages": [AIMessage(content="Done.")]}
    result = middleware.after_agent(state, runtime)
    assert result is None


# ---------------------------------------------------------------------------
# 2. Permission Reporting Helper
# ---------------------------------------------------------------------------

def test_hook_decided_permission() -> None:
    state_allowed = {
        "_hooks_pre_tool_outcomes": {
            "call-1": {"behavior": "allow", "context": []},
            "call-2": {"behavior": "deny", "reason": "blocked", "context": []},
            "call-3": {"behavior": "none", "context": []},
        }
    }
    assert hook_decided_permission(state_allowed, "call-1") is True
    assert hook_decided_permission(state_allowed, "call-2") is True
    assert hook_decided_permission(state_allowed, "call-3") is False
    assert hook_decided_permission(state_allowed, "call-4") is False
    assert hook_decided_permission(None, "call-1") is False


# ---------------------------------------------------------------------------
# 3. Tool Wire Name Mapping
# ---------------------------------------------------------------------------

def test_to_wire_tool_name_native() -> None:
    assert to_wire_tool_name("execute") == "Bash"
    assert to_wire_tool_name("read_file") == "Read"
    assert to_wire_tool_name("edit_file") == "Edit"
    assert to_wire_tool_name("write_file") == "Write"
    assert to_wire_tool_name("glob") == "Glob"
    assert to_wire_tool_name("grep") == "Grep"
    assert to_wire_tool_name("ls") == "LS"
    assert to_wire_tool_name("custom_tool") == "custom_tool"


def test_to_wire_tool_name_mcp() -> None:
    assert format_mcp_wire_name("github", "create_issue") == "mcp__github__create_issue"
    assert (
        to_wire_tool_name("github_create_issue", mcp_server="github")
        == "mcp__github__create_issue"
    )
    assert to_wire_tool_name("mcp__server__tool") == "mcp__server__tool"


def test_to_wire_call_projection() -> None:
    call = ToolCallData(
        id="call-1",
        name="read_file",
        args={"file_path": "/tmp/test.txt", "offset": 0, "limit": 10},
    )
    wire_name, wire_input = to_wire_call(call)
    assert wire_name == "Read"
    assert wire_input == {"file_path": "/tmp/test.txt", "offset": 1, "limit": 10}


# ---------------------------------------------------------------------------
# 4. Interrupt Transport Serialization & Resume Parsing
# ---------------------------------------------------------------------------

def test_interrupt_payload_serialization_roundtrip() -> None:
    invocation_id = uuid4()
    context = HookContext(
        thread_id="thread-123",
        cwd=Path("/workspace"),
        approval_mode=ApprovalMode.MANUAL,
    )
    event = PreToolUseEvent(
        event=HookEvent.PRE_TOOL_USE,
        call=ToolCallData(id="c1", name="execute", args={"command": "ls"}),
    )
    request = HookInvocationRequest(
        protocol_version=1,
        invocation_id=invocation_id,
        snapshot_id="snap-1",
        run_id="run-1",
        invocation=HookInvocation(context=context, event=event),
        deadline=datetime.now(),
    )

    payload = build_hook_interrupt_payload(request)
    parsed_request = parse_hook_interrupt_payload(payload)

    assert parsed_request is not None
    assert parsed_request.invocation_id == invocation_id
    assert parsed_request.snapshot_id == "snap-1"
    assert parsed_request.invocation.event.event == HookEvent.PRE_TOOL_USE


def test_resume_value_parsing_valid_and_invalid() -> None:
    invocation_id = uuid4()
    snapshot_id = "snap-1"
    decision = PreToolUseDecision(
        event=HookEvent.PRE_TOOL_USE,
        permission=PermissionEffect(behavior="allow"),
    )
    response = HookInvocationResponse(
        protocol_version=1,
        invocation_id=invocation_id,
        snapshot_id=snapshot_id,
        decision=decision,
    )

    resume_dict = build_hook_resume_value(response)
    parsed_response = parse_hook_resume_value(
        resume_dict,
        invocation_id=invocation_id,
        snapshot_id=snapshot_id,
    )
    assert parsed_response.decision.event == HookEvent.PRE_TOOL_USE

    # Mismatched invocation_id must raise ValueError
    with pytest.raises(ValueError, match="Resume invocation id"):
        parse_hook_resume_value(
            resume_dict,
            invocation_id=uuid4(),
            snapshot_id=snapshot_id,
        )


# ---------------------------------------------------------------------------
# 5. PostToolUseEvent Construction from Tool Message & Command
# ---------------------------------------------------------------------------

def test_post_tool_use_event_from_tool_message() -> None:
    call = ToolCallData(id="c1", name="ls", args={})
    msg = ToolMessage(content="file1.py\nfile2.py", tool_call_id="c1")
    event = PostToolUseEvent.from_tool_result(msg, call=call, duration_ms=15)

    assert event.event == HookEvent.POST_TOOL_USE
    assert event.duration_ms == 15
    assert isinstance(event.result, dict)
    assert event.result.get("content") == "file1.py\nfile2.py"
