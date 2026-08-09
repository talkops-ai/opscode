"""Tests for CLI argument parsing and validation.

Verifies that ``dcoder`` CLI flags are parsed correctly and that mutually
exclusive or conditionally-required flag combinations are rejected.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from dcoder.cli.main import build_version_text, parse_args, _validate_args


class TestParseArgs:
    """Verify argparse produces the correct namespace for each flag."""

    def test_no_args_is_interactive(self):
        """No args → interactive mode (no non_interactive_message)."""
        with patch("sys.argv", ["dcoder"]):
            args = parse_args()
        assert args.non_interactive_message is None
        assert args.auto_approve is False

    def test_non_interactive_with_dash_n(self):
        """-n "msg" → non_interactive_message populated."""
        with patch("sys.argv", ["dcoder", "-n", "summarize README"]):
            args = parse_args()
        assert args.non_interactive_message == "summarize README"

    def test_positional_prompt(self):
        """Positional prompt is stored in args.prompt."""
        with patch("sys.argv", ["dcoder", "deploy vpc"]):
            args = parse_args()
        assert args.prompt == "deploy vpc"

    def test_model_flag(self):
        """-M anthropic:claude → model parsed."""
        with patch("sys.argv", ["dcoder", "-M", "anthropic:claude-3"]):
            args = parse_args()
        assert args.model == "anthropic:claude-3"

    def test_auto_approve(self):
        """--auto-approve → True."""
        with patch("sys.argv", ["dcoder", "--auto-approve"]):
            args = parse_args()
        assert args.auto_approve is True

    def test_shell_allow_list(self):
        """--shell-allow-list stores raw string."""
        with patch("sys.argv", ["dcoder", "--shell-allow-list", "terraform,kubectl"]):
            args = parse_args()
        assert args.shell_allow_list == "terraform,kubectl"

    def test_resume_thread(self):
        """-r thread-123 → resume_thread populated."""
        with patch("sys.argv", ["dcoder", "-r", "thread-123"]):
            args = parse_args()
        assert args.resume_thread == "thread-123"

    def test_max_turns(self):
        """--max-turns 5 → int."""
        with patch("sys.argv", ["dcoder", "-n", "test", "--max-turns", "5"]):
            args = parse_args()
        assert args.max_turns == 5

    def test_timeout(self):
        """--timeout 120 → float."""
        with patch("sys.argv", ["dcoder", "-n", "test", "--timeout", "120"]):
            args = parse_args()
        assert args.timeout == 120.0

    def test_rubric_flags(self):
        """--rubric, --rubric-model, --rubric-max-iterations parsed."""
        with patch("sys.argv", [
            "dcoder", "-n", "test",
            "--rubric", "tests pass",
            "--rubric-model", "gemini:flash",
            "--rubric-max-iterations", "3",
        ]):
            args = parse_args()
        assert args.rubric == "tests pass"
        assert args.rubric_model == "gemini:flash"
        assert args.rubric_max_iterations == 3

    def test_goal_flag(self):
        """--goal stores objective text."""
        with patch("sys.argv", ["dcoder", "--goal", "add OAuth handling"]):
            args = parse_args()
        assert args.goal == "add OAuth handling"

    def test_mcp_flags(self):
        """--no-mcp, --mcp-config, --trust-project-mcp."""
        with patch("sys.argv", ["dcoder", "--no-mcp"]):
            args = parse_args()
        assert args.no_mcp is True

        with patch("sys.argv", ["dcoder", "--mcp-config", "/path/to/config.json"]):
            args = parse_args()
        assert args.mcp_config == "/path/to/config.json"

        with patch("sys.argv", ["dcoder", "--trust-project-mcp"]):
            args = parse_args()
        assert args.trust_project_mcp is True

    def test_verbose_flag(self):
        """--verbose → True."""
        with patch("sys.argv", ["dcoder", "--verbose"]):
            args = parse_args()
        assert args.verbose is True

    def test_quiet_flag(self):
        """--quiet → True (requires -n for validation, but parsing works)."""
        with patch("sys.argv", ["dcoder", "-n", "test", "--quiet"]):
            args = parse_args()
        assert args.quiet is True

    def test_agent_flag(self):
        """-a custom-agent → agent identity."""
        with patch("sys.argv", ["dcoder", "-a", "custom-agent"]):
            args = parse_args()
        assert args.agent == "custom-agent"


class TestValidateArgs:
    """Verify _validate_args rejects invalid flag combinations."""

    def _make_args(self, **overrides):
        """Build a minimal namespace for validation."""
        import argparse
        defaults = {
            "non_interactive_message": None,
            "quiet": False,
            "no_stream": False,
            "max_turns": None,
            "timeout": None,
            "rubric": None,
            "rubric_model": None,
            "rubric_max_iterations": None,
            "goal": None,
            "no_mcp": False,
            "mcp_config": None,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_quiet_without_non_interactive_exits(self):
        """--quiet without -n → sys.exit(2)."""
        args = self._make_args(quiet=True)
        with pytest.raises(SystemExit, match="2"):
            _validate_args(args)

    def test_no_stream_without_non_interactive_exits(self):
        """--no-stream without -n → sys.exit(2)."""
        args = self._make_args(no_stream=True)
        with pytest.raises(SystemExit, match="2"):
            _validate_args(args)

    def test_max_turns_without_non_interactive_exits(self):
        """--max-turns without -n → sys.exit(2)."""
        args = self._make_args(max_turns=5)
        with pytest.raises(SystemExit, match="2"):
            _validate_args(args)

    def test_timeout_without_non_interactive_exits(self):
        """--timeout without -n → sys.exit(2)."""
        args = self._make_args(timeout=120.0)
        with pytest.raises(SystemExit, match="2"):
            _validate_args(args)

    def test_rubric_without_non_interactive_exits(self):
        """--rubric without -n → sys.exit(2)."""
        args = self._make_args(rubric="tests pass")
        with pytest.raises(SystemExit, match="2"):
            _validate_args(args)

    def test_goal_with_non_interactive_exits(self):
        """--goal with -n → sys.exit(2) (interactive only)."""
        args = self._make_args(goal="add OAuth", non_interactive_message="test")
        with pytest.raises(SystemExit, match="2"):
            _validate_args(args)

    def test_no_mcp_and_mcp_config_mutually_exclusive(self):
        """--no-mcp + --mcp-config → sys.exit(2)."""
        args = self._make_args(no_mcp=True, mcp_config="/path/to/config")
        with pytest.raises(SystemExit, match="2"):
            _validate_args(args)

    def test_valid_non_interactive_passes(self):
        """Valid -n + --quiet + --max-turns → no error."""
        args = self._make_args(
            non_interactive_message="test",
            quiet=True,
            max_turns=5,
            timeout=120.0,
        )
        _validate_args(args)  # Should not raise


class TestBuildVersionText:
    """Verify version string format."""

    def test_contains_dcoder(self):
        text = build_version_text()
        assert "dcoder" in text

    def test_has_version_number(self):
        text = build_version_text()
        # Should have at least "dcoder X.Y.Z" pattern
        parts = text.split()
        assert len(parts) >= 2
