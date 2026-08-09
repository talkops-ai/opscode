"""Unit tests for DCoder CLI options parsing and validation."""

from __future__ import annotations

import pytest
import sys
from unittest.mock import patch

from dcoder.cli.main import parse_args, _validate_args, non_negative_int, positive_int


def test_positive_int_validator():
    assert positive_int("5") == 5
    with pytest.raises(Exception):
        positive_int("0")
    with pytest.raises(Exception):
        positive_int("-3")


def test_non_negative_int_validator():
    assert non_negative_int("0") == 0
    assert non_negative_int("10") == 10
    with pytest.raises(Exception):
        non_negative_int("-1")


def test_parse_args_all_matrix_flags():
    test_args = [
        "dcoder",
        "-r", "thread-123",
        "-a", "devops_agent",
        "-M", "claude-opus-4-7",
        "--model-params", '{"temperature": 0.5}',
        "--max-retries", "3",
        "--profile-override", '{"max_input_tokens": 8192}',
        "-m", "hello agent",
        "-s", "docker",
        "--startup-cmd", "echo starting",
        "-n", "run task",
        "-q",
        "--no-stream",
        "--max-turns", "10",
        "--timeout", "60",
        "--rubric", "tests pass",
        "--rubric-model", "claude-haiku",
        "--rubric-max-iterations", "2",
        "--recursion-limit", "500",
        "-y",
        "-S", "git status,ls",
        "--sandbox", "agentcore",
        "--sandbox-id", "sb-123",
        "--sandbox-snapshot-name", "snap-1",
        "--sandbox-setup", "setup.sh",
        "--mcp-config", "mcp.json",
        "--trust-project-mcp",
        "--trust-project-hooks",
        "--acp",
    ]
    with patch.object(sys, "argv", test_args):
        args = parse_args()
        assert args.resume_thread == "thread-123"
        assert args.agent == "devops_agent"
        assert args.model == "claude-opus-4-7"
        assert args.model_params == '{"temperature": 0.5}'
        assert args.max_retries == 3
        assert args.profile_override == '{"max_input_tokens": 8192}'
        assert args.initial_prompt == "hello agent"
        assert args.initial_skill == "docker"
        assert args.startup_cmd == "echo starting"
        assert args.non_interactive_message == "run task"
        assert args.quiet is True
        assert args.no_stream is True
        assert args.max_turns == 10
        assert args.timeout == 60
        assert args.rubric == "tests pass"
        assert args.rubric_model == "claude-haiku"
        assert args.rubric_max_iterations == 2
        assert args.recursion_limit == 500
        assert args.auto_approve is True
        assert args.shell_allow_list == "git status,ls"
        assert args.sandbox == "agentcore"
        assert args.sandbox_id == "sb-123"
        assert args.sandbox_snapshot_name == "snap-1"
        assert args.sandbox_setup == "setup.sh"
        assert args.mcp_config == "mcp.json"
        assert args.trust_project_mcp is True
        assert args.trust_project_hooks is True
        assert args.acp is True


def test_validate_args_quiet_requires_non_interactive():
    test_args = ["dcoder", "-q"]
    with patch.object(sys, "argv", test_args):
        args = parse_args()
        with pytest.raises(SystemExit):
            _validate_args(args)


def test_validate_args_no_mcp_exclusive_mcp_config():
    test_args = ["dcoder", "-n", "task", "--no-mcp", "--mcp-config", "mcp.json"]
    with patch.object(sys, "argv", test_args):
        args = parse_args()
        with pytest.raises(SystemExit):
            _validate_args(args)
