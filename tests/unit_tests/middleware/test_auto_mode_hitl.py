"""Unit tests for AutoModeHITLMiddleware fast-path and classifier logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from dcoder.middleware.auto_mode_hitl import (
    AutoDecision,
    AutoDecisionBatch,
    AutoDecisionCategory,
    _deterministic_allow,
    _fixed_repo_command_allowed,
    _is_sensitive_write_path,
    _routine_write_allowed,
    mcp_tool_is_coherently_read_only,
    sanitize_auto_reason,
)


def test_mcp_tool_is_coherently_read_only():
    tool_read_only = MagicMock()
    tool_read_only.metadata = {"readOnlyHint": True, "destructiveHint": False}
    assert mcp_tool_is_coherently_read_only(tool_read_only)

    tool_destructive = MagicMock()
    tool_destructive.metadata = {"readOnlyHint": True, "destructiveHint": True}
    assert not mcp_tool_is_coherently_read_only(tool_destructive)

    tool_no_metadata = MagicMock()
    tool_no_metadata.metadata = None
    assert not mcp_tool_is_coherently_read_only(tool_no_metadata)


def test_is_sensitive_write_path(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()

    safe_file = root / "src" / "main.py"
    assert not _is_sensitive_write_path(root, safe_file)

    git_file = root / ".git" / "config"
    assert _is_sensitive_write_path(root, git_file)

    env_file = root / ".env"
    assert _is_sensitive_write_path(root, env_file)

    out_of_bounds = tmp_path / "outside.txt"
    assert _is_sensitive_write_path(root, out_of_bounds)


from langchain_core.messages import ToolCall


def test_routine_write_allowed(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()

    call_py: ToolCall = {"name": "write_file", "args": {"file_path": "src/app.py"}, "id": "1", "type": "tool_call"}
    assert _routine_write_allowed(root, call_py)

    call_tf: ToolCall = {"name": "edit_file", "args": {"TargetFile": "modules/s3/variables.tf"}, "id": "tf-1", "type": "tool_call"}
    assert _routine_write_allowed(root, call_tf)

    call_tf_path: ToolCall = {"name": "edit_file", "args": {"path": "main.tf"}, "id": "tf-2", "type": "tool_call"}
    assert _routine_write_allowed(root, call_tf_path)

    call_hcl: ToolCall = {"name": "write_file", "args": {"path": "terragrunt.hcl"}, "id": "hcl-1", "type": "tool_call"}
    assert _routine_write_allowed(root, call_hcl)

    call_tmpl: ToolCall = {"name": "write_file", "args": {"file": "template.j2"}, "id": "tmpl-1", "type": "tool_call"}
    assert _routine_write_allowed(root, call_tmpl)

    call_env: ToolCall = {"name": "write_file", "args": {"file_path": ".env"}, "id": "2", "type": "tool_call"}
    assert not _routine_write_allowed(root, call_env)

    call_sh: ToolCall = {"name": "write_file", "args": {"file_path": "scripts/deploy.sh"}, "id": "3", "type": "tool_call"}
    assert not _routine_write_allowed(root, call_sh)


def test_deterministic_allow_tools(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()

    call_tf: ToolCall = {"name": "edit_file", "args": {"TargetFile": "variables.tf"}, "id": "1", "type": "tool_call"}
    assert _deterministic_allow(root, call_tf, None, (), None)

    call_search: ToolCall = {"name": "web_search", "args": {"query": "terraform aws s3"}, "id": "2", "type": "tool_call"}
    assert _deterministic_allow(root, call_search, None, (), None)

    call_fetch: ToolCall = {"name": "fetch_url", "args": {"url": "https://example.com"}, "id": "3", "type": "tool_call"}
    assert _deterministic_allow(root, call_fetch, None, (), None)

    call_task: ToolCall = {"name": "task", "args": {"description": "audit"}, "id": "4", "type": "tool_call"}
    assert _deterministic_allow(root, call_task, None, (), None)


def test_fixed_repo_command_allowed(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()

    assert _fixed_repo_command_allowed("git status", root)
    assert _fixed_repo_command_allowed("git diff", root)
    assert _fixed_repo_command_allowed("git log -n 5", root)

    assert not _fixed_repo_command_allowed("git push origin main", root)
    assert not _fixed_repo_command_allowed("rm -rf /", root)
    assert not _fixed_repo_command_allowed("git status && rm -rf .", root)


def test_sanitize_auto_reason():
    raw_reason = "Denied: API_KEY=secret12345678 access to http://user:pass@example.com/api"
    sanitized = sanitize_auto_reason(raw_reason, known_secrets=["secret12345678"])
    assert "secret12345678" not in sanitized
    assert "[redacted]" in sanitized


def test_auto_decision_models():
    decision = AutoDecision(
        tool_call_id="call-1",
        decision="deny",
        category=AutoDecisionCategory.DESTRUCTIVE_ACTION,
        reason="Action attempts to modify protected file .env",
    )
    assert decision.decision == "deny"
    assert decision.category == AutoDecisionCategory.DESTRUCTIVE_ACTION

    batch = AutoDecisionBatch(decisions=[decision])
    assert len(batch.decisions) == 1
