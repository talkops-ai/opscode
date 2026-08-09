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


def test_routine_write_allowed(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()

    call_py = {"name": "write_file", "args": {"file_path": "src/app.py"}}
    assert _routine_write_allowed(root, call_py)

    call_env = {"name": "write_file", "args": {"file_path": ".env"}}
    assert not _routine_write_allowed(root, call_env)

    call_sh = {"name": "write_file", "args": {"file_path": "scripts/deploy.sh"}}
    assert not _routine_write_allowed(root, call_sh)


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
