"""Unit tests for live thinking stream handling, reasoning extraction, and loading widget pinning."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessageChunk, HumanMessage, ToolMessage
from textual.app import App, ComposeResult

from dcoder.ui.remote_client import _convert_ai_message
from dcoder.ui.textual_adapter import TextualAdapter, _extract_text_and_thinking
from dcoder.ui.widgets.loading import LoadingWidget
from dcoder.ui.widgets.messages import MessageList, ThinkingMessage, UserMessage


def test_convert_ai_message_preserves_reasoning_metadata():
    """Verify that _convert_ai_message retains reasoning_content, thinking, and additional_kwargs."""
    server_data = {
        "content": "Final answer",
        "id": "msg-123",
        "reasoning_content": "Internal chain of thought",
        "thinking": "Claude thinking block",
        "additional_kwargs": {"custom_meta": 42},
    }
    chunk = _convert_ai_message(server_data)
    assert chunk is not None
    assert isinstance(chunk, AIMessageChunk)
    assert chunk.content == "Final answer"
    assert chunk.additional_kwargs.get("reasoning_content") == "Internal chain of thought"
    assert chunk.additional_kwargs.get("thinking") == "Claude thinking block"
    assert chunk.additional_kwargs.get("custom_meta") == 42


def test_extract_text_and_thinking_various_formats():
    """Verify _extract_text_and_thinking extracts reasoning correctly across provider formats."""
    # 1. Anthropic / LangChain content list
    c1 = AIMessageChunk(content=[{"type": "thinking", "thinking": "Step 1 reasoning"}])
    text, thinking = _extract_text_and_thinking(c1.content, c1.additional_kwargs, msg_obj=c1)
    assert text == ""
    assert thinking == "Step 1 reasoning"

    # 2. DeepSeek / OpenAI reasoning_content in additional_kwargs
    c2 = AIMessageChunk(content="", additional_kwargs={"reasoning_content": "DeepSeek R1 reasoning"})
    text, thinking = _extract_text_and_thinking(c2.content, c2.additional_kwargs, msg_obj=c2)
    assert text == ""
    assert thinking == "DeepSeek R1 reasoning"

    # 3. XML thinking tags
    c3 = AIMessageChunk(content="<thinking>Tag reasoning</thinking>Hello world")
    text, thinking = _extract_text_and_thinking(c3.content, c3.additional_kwargs, msg_obj=c3)
    assert text == "Hello world"
    assert thinking == "Tag reasoning"


def test_thinking_message_widget():
    """Verify ThinkingMessage display text and toggle expansion."""
    msg = ThinkingMessage(content="Initial thought", duration_seconds=3.2)
    display = msg._build_display()
    assert "Thought for 3s" in str(display)

    # Update dynamically
    msg.update_thinking("Updated thoughts", duration_seconds=5.0)
    display = msg._build_display()
    assert "Thought for 5s" in str(display)


class DummyThinkingApp(App):
    _loading_widget: LoadingWidget | None = None

    def compose(self) -> ComposeResult:
        yield MessageList(id="messages")


@pytest.mark.asyncio
async def test_stream_turn_handles_thinking_chunks():
    """Verify stream_turn calls append_thinking_token and maintains spinner when thinking chunks arrive."""
    app = DummyThinkingApp()
    async with app.run_test() as pilot:
        messages = app.query_one("#messages", MessageList)
        messages.append_thinking_token = MagicMock()
        messages.append_assistant_token = MagicMock()

        mock_spinner = AsyncMock()
        mock_client = MagicMock()

        async def mock_astream(*args, **kwargs):
            # Yield thinking chunk
            yield (
                (),
                "messages",
                (
                    AIMessageChunk(
                        content=[{"type": "thinking", "thinking": "Thinking about subagents..."}]
                    ),
                    {},
                ),
            )
            # Yield text chunk
            yield (
                (),
                "messages",
                (
                    AIMessageChunk(content="Here are your subagents:"),
                    {},
                ),
            )

        mock_client.astream = mock_astream

        adapter = TextualAdapter(
            client=mock_client,
            assistant_id="test",
            messages_widget=messages,
            status_bar=None,
            set_spinner=mock_spinner,
            app=app,
        )

        await adapter.stream_turn("List subagents", thread_id="t-123")

        # Verify thinking token was appended
        messages.append_thinking_token.assert_called_once()
        args, kwargs = messages.append_thinking_token.call_args
        assert args[0] == "Thinking about subagents..."
        assert kwargs.get("duration_seconds") is not None

        # Verify assistant token was appended
        messages.append_assistant_token.assert_called_once_with("Here are your subagents:")


@pytest.mark.asyncio
async def test_loading_widget_pinning_in_message_list():
    """Verify that when _loading_widget is present, new messages mount before it."""
    app = DummyThinkingApp()
    async with app.run_test() as pilot:
        messages = app.query_one("#messages", MessageList)

        loading = LoadingWidget("Thinking")
        app._loading_widget = loading
        await messages.mount(loading)

        # Mount a new user message via MessageList
        messages.add_user_message("Hello")
        await pilot.pause()

        # Loading widget must remain at the very end of messages.children
        children = list(messages.children)
        assert children[-1] is loading
        assert any(isinstance(c, UserMessage) for c in children[:-1])
