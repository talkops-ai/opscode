import pytest
from dcoder.middleware.tool_filter import ToolFilterMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage


def test_tool_filter_middleware_allows_whitelisted():
    middleware = ToolFilterMiddleware(allowed_patterns=["mcp__kubectl__*", "read_file", "write_file"])

    assert middleware.is_tool_allowed("mcp__kubectl__get_pods") is True
    assert middleware.is_tool_allowed("read_file") is True
    assert middleware.is_tool_allowed("write_file") is True
    assert middleware.is_tool_allowed("delete") is False
    assert middleware.is_tool_allowed("execute") is False


def test_tool_filter_middleware_blocks_unauthorized_call():
    middleware = ToolFilterMiddleware(allowed_patterns=["read_file"])

    from unittest.mock import MagicMock
    from typing import Any, cast
    
    req = ToolCallRequest(
        tool_call={"name": "delete", "args": {"path": "/tmp/foo"}, "id": "call_123"},
        tool=cast(Any, MagicMock()),
        state={},
        runtime=cast(Any, MagicMock()),
    )

    result = middleware._validate_tool_call(req)
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert "Tool call rejected" in result.content


def test_tool_filter_middleware_alias_expansion():
    middleware = ToolFilterMiddleware(allowed_patterns=["Read", "Write", "Edit", "dir_list", "search_*", "get_*"])

    assert middleware.is_tool_allowed("read_file") is True
    assert middleware.is_tool_allowed("view_file") is True
    assert middleware.is_tool_allowed("write_to_file") is True
    assert middleware.is_tool_allowed("replace_file_content") is True
    assert middleware.is_tool_allowed("multi_replace_file_content") is True
    assert middleware.is_tool_allowed("dir_list") is True
    assert middleware.is_tool_allowed("search_providers") is True
    assert middleware.is_tool_allowed("get_provider_schema") is True
    assert middleware.is_tool_allowed("search_resources") is True
    assert middleware.is_tool_allowed("get_resource_schema") is True
    assert middleware.is_tool_allowed("run_command") is False

