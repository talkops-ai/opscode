"""Tests for agent factory utilities and configuration logic."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, MagicMock

from dcoder.agent.factory import (
    CLIContextSchema,
    _interrupt_predicate,
    _should_interrupt_tool_call,
    _format_description,
    _resolve_ptc_option,
    INTERPRETER_PTC_SAFE_PRESET,
)


class TestShouldInterruptToolCall:
    def test_respects_auto_approve_in_context_dict(self):
        """Returns False if auto_approve is True in context dictionary."""
        request = Mock(runtime=Mock(context={"auto_approve": True}))
        assert not _should_interrupt_tool_call(request)

    def test_respects_auto_approve_in_context_schema(self):
        """Returns False if auto_approve is True on CLIContextSchema."""
        ctx = CLIContextSchema(auto_approve=True)
        request = Mock(runtime=Mock(context=ctx, store=None))
        assert not _should_interrupt_tool_call(request)

    def test_interrupts_by_default(self):
        """Returns True if auto_approve is not set or False."""
        request = Mock(runtime=Mock(context={"auto_approve": False}))
        assert _should_interrupt_tool_call(request)
        
        ctx_schema = CLIContextSchema(auto_approve=False)
        request = Mock(runtime=Mock(context=ctx_schema, store=None))
        assert _should_interrupt_tool_call(request)
        
        request = Mock(runtime=None)
        assert _should_interrupt_tool_call(request)

    def test_never_interrupts_agents_md(self):
        """Always returns False for AGENTS.md writes, ignoring auto_approve."""
        request = Mock(
            runtime=None,
            action={"args": {"path": "/workspace/.agents/AGENTS.md"}}
        )
        assert not _should_interrupt_tool_call(request)


class TestFormatDescription:
    def test_format_execute(self):
        tool_call = {"name": "execute", "args": {"command": "ls -l"}}
        assert _format_description(tool_call) == "Shell command execution: ls -l"

    def test_format_destructive_execute(self):
        tool_call = {"name": "execute", "args": {"command": "terraform destroy"}}
        assert "⚠️ DESTRUCTIVE" in _format_description(tool_call)
        
        tool_call = {"name": "execute", "args": {"command": "kubectl delete pod"}}
        assert "⚠️ DESTRUCTIVE" in _format_description(tool_call)

    def test_format_apply_execute(self):
        tool_call = {"name": "execute", "args": {"command": "terraform apply"}}
        assert "create/modify" in _format_description(tool_call)

    def test_format_file_ops(self):
        tool_call = {"name": "write_file", "args": {"path": "/test.txt"}}
        assert "Write to file: /test.txt" in _format_description(tool_call)
        
        tool_call = {"name": "delete", "args": {"TargetFile": "/test.txt"}}
        assert "⚠️ DESTRUCTIVE: Delete file: /test.txt" in _format_description(tool_call)

    def test_format_fallback(self):
        tool_call = {"name": "unknown_tool", "args": {"foo": "bar"}}
        assert "Execute tool 'unknown_tool'" in _format_description(tool_call)


class TestResolvePtcOption:
    def test_resolve_ptc_none_or_false(self):
        assert _resolve_ptc_option(None, tools=[], acknowledge_unsafe=False, auto_approve=False) is None
        assert _resolve_ptc_option(False, tools=[], acknowledge_unsafe=False, auto_approve=False) is None
        assert _resolve_ptc_option([], tools=[], acknowledge_unsafe=False, auto_approve=False) is None

    def test_resolve_ptc_safe_preset(self):
        res = _resolve_ptc_option("safe", tools=[], acknowledge_unsafe=False, auto_approve=False)
        assert res == sorted(INTERPRETER_PTC_SAFE_PRESET)

    def test_resolve_ptc_all_preset_without_acknowledgment(self):
        with pytest.raises(ValueError, match="HITL approval"):
            _resolve_ptc_option("all", tools=[], acknowledge_unsafe=False, auto_approve=False)

    def test_resolve_ptc_all_preset_with_acknowledgment(self):
        tools = [{"name": "execute"}, {"name": "read_file"}]
        res = _resolve_ptc_option("all", tools=tools, acknowledge_unsafe=True, auto_approve=False)
        assert res == sorted(["execute", "read_file"])

    def test_resolve_ptc_list(self):
        res = _resolve_ptc_option(["read_file", "glob"], tools=[], acknowledge_unsafe=False, auto_approve=False)
        assert res == ["glob", "read_file"]
        
    def test_resolve_ptc_list_with_safe(self):
        res = _resolve_ptc_option(["safe", "custom_tool"], tools=[], acknowledge_unsafe=False, auto_approve=False)
        expected = set(INTERPRETER_PTC_SAFE_PRESET)
        expected.add("custom_tool")
        assert res == sorted(expected)

    def test_resolve_ptc_list_blocks_unsafe_without_ack(self):
        with pytest.raises(ValueError, match="HITL approval"):
            _resolve_ptc_option(["execute"], tools=[], acknowledge_unsafe=False, auto_approve=False)

    def test_resolve_ptc_blocks_task_without_ack(self):
        from dcoder.agent.factory import _INTERPRETER_WRITE_TOOLS
        assert "task" in _INTERPRETER_WRITE_TOOLS
        assert "start_async_task" in _INTERPRETER_WRITE_TOOLS
        assert "update_async_task" in _INTERPRETER_WRITE_TOOLS
        assert "cancel_async_task" in _INTERPRETER_WRITE_TOOLS

        with pytest.raises(ValueError, match="HITL approval"):
            _resolve_ptc_option(["task"], tools=[], acknowledge_unsafe=False, auto_approve=False)


def test_format_task_description_formatting():
    from dcoder.agent.factory import _format_description

    tool_call = {
        "name": "task",
        "args": {
            "subagent_type": "researcher",
            "description": "Investigate cluster health and report metrics.",
        },
    }

    formatted = _format_description(tool_call)
    assert "Subagent Type: researcher" in formatted
    assert "⚠️ Subagent will have access to file operations and shell commands ⚠️" in formatted
    assert "Task Instructions:" in formatted
    assert "Investigate cluster health and report metrics." in formatted


def test_format_task_description_truncation():
    from dcoder.agent.factory import _format_description

    long_instructions = "x" * 600
    tool_call = {
        "name": "task",
        "args": {
            "subagent_type": "k8s-auditor",
            "description": long_instructions,
        },
    }

    formatted = _format_description(tool_call)
    assert "Subagent Type: k8s-auditor" in formatted
    assert "x" * 500 in formatted
    assert "..." in formatted
    assert len(formatted) < len(long_instructions) + 200

