"""Unit tests for tool streaming data layer."""

from __future__ import annotations

import pytest
from dcoder.ui.widgets._tool_stream import ToolCallBuffer, tool_call_buffer_key

def test_tool_call_buffer_streaming_sequence():
    """Verify state transitions and chunk accumulation during streaming."""
    buffers: dict[str | int, ToolCallBuffer] = {}
    
    # Simulate an incoming LangGraph tool call chunk
    key = tool_call_buffer_key(index=0, tool_id="tc_123", count=1)
    if key not in buffers:
        buffers[key] = ToolCallBuffer()
        
    buffers[key].ingest(name="execute", tool_id="tc_123", args='{"cmd": "')
    
    assert buffers[key].name == "execute"
    assert buffers[key].tool_id == "tc_123"
    assert buffers[key].args_parts == ['{"cmd": "']
    
    # Add argument chunks
    buffers[key].ingest(name=None, tool_id="tc_123", args='ls -la"}')
    
    # Test finalizing the call
    parsed = buffers[key].parse_args()
    assert parsed == {"cmd": "ls -la"}

def test_tool_call_buffer_multiple_concurrent_calls():
    """Verify tool call buffer handles multiple concurrent tool calls."""
    buffers: dict[str | int, ToolCallBuffer] = {}
    
    key1 = tool_call_buffer_key(index=0, tool_id="tc_1", count=1)
    key2 = tool_call_buffer_key(index=1, tool_id="tc_2", count=2)
    
    buffers[key1] = ToolCallBuffer()
    buffers[key2] = ToolCallBuffer()
    
    buffers[key1].ingest(name="execute", tool_id="tc_1", args='{"cmd": ')
    buffers[key2].ingest(name="read_file", tool_id="tc_2", args='{"path": "/tmp"}')
    
    buffers[key1].ingest(name=None, tool_id="tc_1", args='"echo"}')
    
    assert buffers[key1].name == "execute"
    assert buffers[key1].parse_args() == {"cmd": "echo"}
    
    assert buffers[key2].name == "read_file"
    assert buffers[key2].parse_args() == {"path": "/tmp"}
