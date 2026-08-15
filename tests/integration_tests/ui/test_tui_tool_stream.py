"""Integration tests for tool output streaming in the TUI."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from textual.app import App
from textual.containers import VerticalScroll

from langchain_core.messages import ToolMessage, AIMessageChunk
from dcoder.ui.widgets.messages import MessageList, ToolGroupSummary, ToolCallMessage, AssistantMessage
from dcoder.ui.textual_adapter import TextualAdapter

from textual.theme import Theme

class DummyApp(App):
    """A minimal Textual app to host the MessageList for integration testing."""
    
    def on_mount(self):
        self.register_theme(
            Theme(
                name="dummy",
                primary="#000",
                variables={
                    "tool": "#888888",
                    "tool-border": "#888888",
                    "tool-hover": "#888888"
                }
            )
        )
        self.theme = "dummy"
        
    def compose(self):
        yield VerticalScroll(MessageList(id="chat"))

@pytest.mark.asyncio
async def test_tool_message_integration():
    """Simulate a tool stream and verify TUI DOM rendering."""
    app = DummyApp()
    
    async with app.run_test() as pilot:
        messages = app.query_one(MessageList)
        
        # Initialize TextualAdapter
        adapter = TextualAdapter(
            app=app,
            client=MagicMock(),
            assistant_id="mock_id",
            messages_widget=messages,
            status_bar=MagicMock()
        )
        
        # 1. Setup an active tool (ToolCallBuffer simulated finishing)
        adapter._active_tools_map["call_123"] = "view_file"
        
        # 2. Simulate streaming a ToolMessage (this should resolve the tool call)
        # Note: ToolMessage now contains content_blocks in newer LangChain versions,
        # which previously caused a bug where its text bled into the AssistantMessage.
        # By passing a list of dicts, LangChain will automatically populate the content_blocks property.
        msg = ToolMessage(
            content=[{"type": "text", "text": "Line 1\nLine 2\nLine 3"}],
            tool_call_id="call_123",
            name="view_file"
        )

        
        # 3. Simulate streaming some assistant text immediately after
        assistant_chunk = AIMessageChunk(
            content="Here is the output."
        )
        
        async def mock_astream(*args, **kwargs):
            yield ((), "messages", (msg, {}))
            yield ((), "messages", (assistant_chunk, {}))
            
        adapter._client.astream = mock_astream

        await adapter.stream_turn(prompt="Test prompt", thread_id="thread_123")
        await pilot.pause()
        
        # Verify ToolGroupSummary was created and contains the tool
        summaries = list(messages.query(ToolGroupSummary))
        assert len(summaries) == 1
        group = summaries[0]
        
        # Verify ToolCallMessage was created and placed in the DOM
        tool_calls = list(messages.query(ToolCallMessage))
        assert len(tool_calls) == 1
        tool_call = tool_calls[0]
        
        # Verify the tool call is inside the collapsible group and is hidden by default
        assert tool_call in group._collapsible
        assert group._collapsed is True
        assert tool_call.display is False
        
        # Ensure the group is in past tense ("Read X lines") because update_tool_result was called!
        assert tool_call.is_pending is False
        
        # Verify the AssistantMessage does NOT contain the tool's raw output
        assistant_msgs = list(messages.query(AssistantMessage))
        assert len(assistant_msgs) == 1
        assistant_msg = assistant_msgs[0]
        
        assert "Here is the output." in assistant_msg._content
        assert "Line 1" not in assistant_msg._content
