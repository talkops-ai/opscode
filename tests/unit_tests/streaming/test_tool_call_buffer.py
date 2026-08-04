"""Tests for streaming tool-call buffer and parsing."""

from __future__ import annotations

import pytest

from dcoder.ui._tool_stream import (
    ToolCallBuffer,
    _exceeds_json_container_depth,
    _looks_structurally_complete,
    tool_call_buffer_key,
)


class TestToolCallBufferKey:
    def test_buffer_key_generation(self):
        """tool_call_buffer_key generates stable keys based on index, id, or count."""
        assert tool_call_buffer_key(index=1, tool_id="call_abc", count=0) == 1
        assert tool_call_buffer_key(index=None, tool_id="call_abc", count=0) == "call_abc"
        assert tool_call_buffer_key(index=None, tool_id=None, count=5) == "unknown-5"


class TestJSONDepthAndCompleteness:
    def test_json_depth_check(self):
        """_exceeds_json_container_depth validates nesting."""
        assert not _exceeds_json_container_depth('{"a": 1}')
        
        deep_json = '{"a": {"b": {"c": 1}}}'
        assert not _exceeds_json_container_depth(deep_json)
        
        # We can't easily trigger the recursion limit in a short test, but we can verify it doesn't fail on normal JSON

    def test_looks_structurally_complete(self):
        """_looks_structurally_complete handles chunks and strings correctly."""
        assert not _looks_structurally_complete('{"a": 1')
        assert _looks_structurally_complete('{"a": 1}')
        
        # Unbalanced (too many closers)
        assert _looks_structurally_complete('{"a": 1}}')
        
        # String escape awareness
        assert not _looks_structurally_complete('{"a": "value}')
        assert not _looks_structurally_complete('{"a": "value\\"')


class TestToolCallBuffer:
    def test_buffer_accumulates_args(self):
        """ingest string fragments correctly appends them."""
        buf = ToolCallBuffer()
        buf.ingest(name="test_tool", tool_id="call_1", args='{"a":')
        buf.ingest(name=None, tool_id="call_1", args=' 1}')
        
        assert buf.name == "test_tool"
        assert buf.tool_id == "call_1"
        assert buf.args is None
        assert buf.args_parts == ['{"a":', ' 1}']
        
        parsed = buf.parse_args()
        assert parsed == {"a": 1}

    def test_buffer_emits_on_complete(self):
        """parse_args returns dict when complete, None when partial."""
        buf = ToolCallBuffer()
        buf.ingest(name="test_tool", tool_id="call_1", args='{"a":')
        assert buf.parse_args() is None
        
        buf.ingest(name=None, tool_id="call_1", args=' 1}')
        assert buf.parse_args() == {"a": 1}

    def test_ingest_whole_args_dict(self):
        """ingest with dict replaces parts."""
        buf = ToolCallBuffer()
        buf.ingest(name="test_tool", tool_id="call_1", args={"a": 1})
        
        assert buf.args == {"a": 1}
        assert buf.args_parts == []
        assert buf.parse_args() == {"a": 1}

    def test_buffer_invariant_checked(self):
        """__post_init__ catches invalid state."""
        with pytest.raises(ValueError, match="cannot hold both args and args_parts"):
            ToolCallBuffer(args={"a": 1}, args_parts=["test"])

    def test_parse_args_wraps_scalar(self):
        """Non-dict JSON is wrapped in {"value": ...}."""
        buf = ToolCallBuffer()
        buf.ingest(name="test", tool_id="id", args='123')
        assert buf.parse_args() == {"value": 123}

    def test_buffer_resets_on_new_id(self):
        """ingest resets state if a new tool_id uses the same buffer."""
        buf = ToolCallBuffer(name="old_tool", tool_id="call_1", args={"a": 1})
        buf.ingest(name="new_tool", tool_id="call_2", args='{"b": 2}')
        
        assert buf.name == "new_tool"
        assert buf.tool_id == "call_2"
        assert buf.args is None
        assert buf.args_parts == ['{"b": 2}']
