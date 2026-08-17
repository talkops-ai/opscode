"""Tests for textual adapter logic."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import Mock, MagicMock

from opscode.ui.textual_adapter import (
    _format_thinking_tags,
    _format_thinking_quote,
    _extract_text_and_thinking,
)


class TestTextualAdapterFormatting:
    def test_format_thinking_tags(self):
        text = "Hello <thinking>world</thinking>!"
        res = _format_thinking_tags(text)
        assert res == "Hello > *Thinking:*\n> world\n\n!"

        text = "Hello <thought>world</thought>!"
        res = _format_thinking_tags(text)
        assert res == "Hello > *Thinking:*\n> world\n\n!"

    def test_format_thinking_quote(self):
        assert _format_thinking_quote("") == ""
        assert _format_thinking_quote("   ") == ""
        assert _format_thinking_quote("thinking text") == "> *Thinking:* thinking text\n\n"

    def test_extract_text_and_thinking_from_kwargs(self):
        content = "hello"
        kwargs = {"thinking": "some thoughts"}
        text, thinking = _extract_text_and_thinking(content, additional_kwargs=kwargs)
        assert text == "hello"
        assert thinking == "some thoughts"

    def test_extract_text_and_thinking_from_metadata(self):
        content = "hello"
        metadata = {"reasoning_content": "some thoughts"}
        text, thinking = _extract_text_and_thinking(content, response_metadata=metadata)
        assert text == "hello"
        assert thinking == "some thoughts"

    def test_extract_text_and_thinking_from_object(self):
        content = "hello"
        msg_obj = Mock(reasoning_content="some thoughts")
        text, thinking = _extract_text_and_thinking(content, msg_obj=msg_obj)
        assert text == "hello"
        assert thinking == "some thoughts"

    def test_extract_text_and_thinking_mixed(self):
        content = "hello"
        msg_obj = Mock(reasoning_content="thought 1")
        kwargs = {"thinking": "thought 2"}
        text, thinking = _extract_text_and_thinking(content, additional_kwargs=kwargs, msg_obj=msg_obj)
        
        assert text == "hello"
        # Since it concatenates thinking parts with double newlines
        assert "thought 1" in thinking
        assert "thought 2" in thinking

class TestTextualAdapterToolMessage:
    @pytest.mark.asyncio
    async def test_tool_message_with_content_blocks_intercepted(self):
        """Verify ToolMessage with content_blocks correctly routes to update_tool_result."""
        from opscode.ui.textual_adapter import TextualAdapter
        from langchain_core.messages import ToolMessage
        
        adapter = TextualAdapter(
            app=MagicMock(),
            client=MagicMock(),
            assistant_id="mock_id",
            status_bar=MagicMock()
        )
        adapter._messages = MagicMock()
        
        # Simulating LangChain's new ToolMessage structure which has content_blocks
        msg = ToolMessage(
            content="Tool output text",
            tool_call_id="call_123",
            name="test_tool"
        )
        # Ensure it has the attribute to trigger the bug if the order was wrong
        assert hasattr(msg, "content_blocks")
        
        async def mock_astream(*args, **kwargs):
            yield ((), "messages", (msg, {}))
            
        adapter._client.astream = mock_astream
        
        await adapter.stream_turn(prompt="Test", thread_id="t1")
        
        # It should update the tool result, NOT append assistant tokens
        adapter._messages.update_tool_result.assert_called_once_with(
            call_id="call_123", result="Tool output text", name="test_tool"
        )
        adapter._messages.append_assistant_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_interrupts_deduplicated(self):
        """Verify that duplicate interrupt events with the same interrupt_id are deduplicated."""
        from opscode.ui.textual_adapter import TextualAdapter

        mock_app = MagicMock()
        loop = asyncio.get_running_loop()
        approval_calls = []

        async def mock_request_approval(action_requests, assistant_id):
            approval_calls.append((action_requests, assistant_id))
            fut = loop.create_future()
            fut.set_result({"type": "approve"})
            return fut

        adapter = TextualAdapter(
            app=mock_app,
            client=MagicMock(),
            assistant_id="mock_id",
            status_bar=MagicMock(),
            request_approval=mock_request_approval,
        )

        mock_interrupt = Mock()
        mock_interrupt.id = "int_123"
        mock_interrupt.value = {
            "action_requests": [{"action": "edit_file", "args": {"file_path": "main.tf"}}]
        }

        async def mock_astream(input_data, *args, **kwargs):
            from langgraph.types import Command
            if isinstance(input_data, Command):
                yield ((), "updates", {})
            else:
                # Emit duplicate interrupt events in the same turn (subagent level and parent level)
                yield ((), "updates", {"__interrupt__": (mock_interrupt,)})
                yield ((), "updates", {"__interrupt__": (mock_interrupt,)})

        adapter._client.astream = mock_astream

        await adapter.stream_turn(prompt="Test", thread_id="t1")

        # Verify request_approval was called EXACTLY ONCE
        assert len(approval_calls) == 1
        assert approval_calls[0][0][0]["action"] == "edit_file"

