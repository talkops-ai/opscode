"""Unit tests for ShellAllowListMiddleware."""

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import ToolMessage

from dcoder.middleware.shell_allow_list import ShellAllowListMiddleware


class TestShellAllowListValidation:
    """Tests for the _validate_tool_call method."""

    def test_non_execute_tool_passes_through(self):
        """Non-execute tools are never intercepted."""
        middleware = ShellAllowListMiddleware(allow_list=["ls"])
        req = MagicMock()
        req.tool_call = {"name": "read_file", "args": {"path": "/foo"}, "id": "tc1"}
        assert middleware._validate_tool_call(req) is None

    def test_empty_allow_list_blocks_all(self):
        """An empty allow-list rejects all shell commands."""
        middleware = ShellAllowListMiddleware(allow_list=[])
        req = MagicMock()
        req.tool_call = {"name": "execute", "args": {"command": "ls"}, "id": "tc1"}
        result = middleware._validate_tool_call(req)
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert "no commands are allowed" in result.content

    def test_allowed_command_passes(self):
        """A command matching the allow-list is allowed through."""
        middleware = ShellAllowListMiddleware(allow_list=["ls", "cat", "grep"])
        req = MagicMock()
        req.tool_call = {"name": "execute", "args": {"command": "ls -la"}, "id": "tc1"}
        assert middleware._validate_tool_call(req) is None

    def test_disallowed_command_blocked(self):
        """A command NOT in the allow-list is blocked."""
        middleware = ShellAllowListMiddleware(allow_list=["ls"])
        req = MagicMock()
        req.tool_call = {"name": "execute", "args": {"command": "rm -rf /"}, "id": "tc1"}
        result = middleware._validate_tool_call(req)
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert "not in the allow-list" in result.content

    def test_devops_safe_commands(self):
        """DevOps read-only commands like terraform validate pass."""
        middleware = ShellAllowListMiddleware(
            allow_list=["terraform validate", "terraform fmt", "helm lint"]
        )
        req = MagicMock()
        req.tool_call = {
            "name": "execute",
            "args": {"command": "terraform validate -json"},
            "id": "tc1",
        }
        assert middleware._validate_tool_call(req) is None

    def test_compound_command_all_segments_must_be_allowed(self):
        """In compound commands (&&), every segment must match."""
        middleware = ShellAllowListMiddleware(allow_list=["ls", "cat"])
        req = MagicMock()
        req.tool_call = {
            "name": "execute",
            "args": {"command": "ls -la && cat file.txt"},
            "id": "tc1",
        }
        assert middleware._validate_tool_call(req) is None

    def test_compound_command_blocks_if_any_segment_disallowed(self):
        """If any segment of a compound command is disallowed, block it."""
        middleware = ShellAllowListMiddleware(allow_list=["ls"])
        req = MagicMock()
        req.tool_call = {
            "name": "execute",
            "args": {"command": "ls -la && rm -rf /"},
            "id": "tc1",
        }
        result = middleware._validate_tool_call(req)
        assert isinstance(result, ToolMessage)
        assert result.status == "error"

    def test_dangerous_patterns_blocked_even_if_prefix_allowed(self):
        """Dangerous shell patterns like $(cmd) are blocked regardless of prefix."""
        middleware = ShellAllowListMiddleware(allow_list=["ls"])
        req = MagicMock()
        req.tool_call = {
            "name": "execute",
            "args": {"command": "ls $(whoami)"},
            "id": "tc1",
        }
        result = middleware._validate_tool_call(req)
        assert isinstance(result, ToolMessage)
        assert result.status == "error"


class TestShellAllowListWrapToolCall:
    """Tests for the synchronous wrap_tool_call method."""

    def test_allowed_calls_handler(self):
        """Allowed commands proceed to the handler."""
        middleware = ShellAllowListMiddleware(allow_list=["ls"])
        req = MagicMock()
        req.tool_call = {"name": "execute", "args": {"command": "ls"}, "id": "tc1"}
        handler = MagicMock(return_value="handler_result")
        result = middleware.wrap_tool_call(req, handler)
        assert result == "handler_result"
        handler.assert_called_once_with(req)

    def test_blocked_skips_handler(self):
        """Blocked commands never call the handler."""
        middleware = ShellAllowListMiddleware(allow_list=["ls"])
        req = MagicMock()
        req.tool_call = {"name": "execute", "args": {"command": "rm -rf /"}, "id": "tc1"}
        handler = MagicMock()
        result = middleware.wrap_tool_call(req, handler)
        handler.assert_not_called()
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
