"""Unit tests for TUI Intermediate Steps & Turn Sequence Architecture.

Verifies strict chronological mounting of assistant text bubbles and tool call widgets,
auto-creation of post-tool text bubbles, thinking block extraction, name fallback guards,
and smart tool display formatting matching reference dcode.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Tuple
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessageChunk, ToolMessage
from textual.app import App, ComposeResult
from dcoder.ui.messages import AssistantMessage, MessageList, ToolCallMessage
from dcoder.ui.textual_adapter import TextualAdapter, _extract_text
from dcoder.ui.tool_display import format_tool_display


class DummyApp(App[None]):
    """Test App container to host MessageList widget in a mounted state."""

    def compose(self) -> ComposeResult:
        yield MessageList()


def test_extract_text_thinking_blocks() -> None:
    """Verify _extract_text handles string and dict thinking/reasoning blocks."""
    # String in additional_kwargs
    res1 = _extract_text("", {"thinking": "Analyzing codebase structure..."})
    assert "> *Thinking:* Analyzing codebase structure..." in res1

    res2 = _extract_text("", {"reasoning_content": "Evaluating dependencies..."})
    assert "> *Thinking:* Evaluating dependencies..." in res2

    # Dict in additional_kwargs
    res3 = _extract_text("", {"thought": {"text": "Thinking deeply..."}})
    assert "> *Thinking:* Thinking deeply..." in res3

    # Structured block list in content
    content_blocks = [
        {"type": "thinking", "text": "Formulating plan..."},
        {"type": "text", "text": "Here is the response."},
    ]
    res4 = _extract_text(content_blocks)
    assert "> *Thinking:* Formulating plan..." in res4
    assert "Here is the response." in res4

    # Dict thinking in block
    content_blocks2 = [
        {"thinking": {"text": "Block thinking dict"}},
    ]
    res5 = _extract_text(content_blocks2)
    assert "> *Thinking:* Block thinking dict" in res5

    # response_metadata thinking
    res6 = _extract_text("", response_metadata={"reasoning_content": "Metadata reasoning"})
    assert "> *Thinking:* Metadata reasoning" in res6

    # Direct attribute on msg_obj
    mock_msg = MagicMock()
    mock_msg.reasoning_content = "Direct reasoning content"
    res7 = _extract_text("", msg_obj=mock_msg)
    assert "> *Thinking:* Direct reasoning content" in res7

    # Inline XML tags
    res8 = _extract_text("<thinking>Inline thinking text</thinking>Response after thinking")
    assert "> *Thinking:* Inline thinking text" in res8
    assert "Response after thinking" in res8


def test_format_tool_display_parity_with_reference_dcode() -> None:
    """Verify format_tool_display smart tool header formatting."""
    from dcoder.ui.tool_display import (
        format_tool_result_summary,
        register_tool_display_name,
    )

    assert format_tool_display("read_file", {"file_path": "README.md"}) == "● Read(README.md)"
    assert format_tool_display("execute", {"command": "pytest"}) == '● Execute("pytest")'
    assert format_tool_display("web_search", {"query": "langchain"}) == '● Search("langchain")'
    assert format_tool_display("grep", {"pattern": "def test", "path": "tests"}) == '● Grep("def test" in tests)'
    assert format_tool_display("ls", {"directory_path": "src"}) == "● Ls(src)"
    assert format_tool_display("ask_user", {"questions": ["Q1", "Q2"]}) == "● Ask(2 questions)"
    assert format_tool_display("task", {"subagent_type": "terraform"}) == "● Task [terraform]"

    # Generic fallback: snake_case -> TitleCase
    assert format_tool_display("deploy_helm_chart", {"chart": "nginx"}) == '● DeployHelmChart("nginx")'
    assert format_tool_display("kubectl_get_pods", {"namespace": "default"}) == '● KubectlGetPods("default")'
    assert format_tool_display("mcp_server_ping", {}) == "● McpServerPing()"

    # Extension API
    register_tool_display_name("custom_tool", "CustomAlias")
    assert format_tool_display("custom_tool", {"arg": "val"}) == '● CustomAlias("val")'

    # Generic summary formatters
    assert format_tool_result_summary("unknown_tool", '["a", "b", "c"]') == "⎿ 3 items returned"
    assert format_tool_result_summary("unknown_tool", '{"status": "ok"}') == "⎿ 1 fields returned"


@pytest.mark.asyncio
async def test_tool_call_message_name_fallback_and_glyphs() -> None:
    """Verify ToolCallMessage name fallbacks and glyph formatting."""
    app = DummyApp()
    async with app.run_test():
        # Fallback when name is None or "None"
        tc1 = ToolCallMessage(None, "call_1", {})  # type: ignore[arg-type]
        assert tc1.tool_name == "tool"

        tc2 = ToolCallMessage("None", "call_2", {})
        assert tc2.tool_name == "tool"

        # Valid name and glyph styling
        tc3 = ToolCallMessage("read_file", "call_3", {"path": "README.md"})
        assert tc3.tool_name == "read_file"
        plain_text = getattr(tc3.render(), "plain", str(tc3.render()))
        assert "● Read(README.md)" in plain_text

        # Success update styling
        tc3.set_result("file content", success=True)
        plain_success = getattr(tc3.render(), "plain", str(tc3.render()))
        assert "● Read(README.md)" in plain_success
        assert "⎿ Read 1 lines" in plain_success
        assert tc3._status == "success"

        # Error update styling
        tc4 = ToolCallMessage("exec", "call_4", {"command": "ls"})
        tc4.set_result("command failed", success=False)
        plain_err = getattr(tc4.render(), "plain", str(tc4.render()))
        assert '● Execute("ls")' in plain_err
        assert tc4._status == "error"

        # Test on_click click-to-expand preserves tool name formatting
        tc3.on_click()
        assert tc3._expanded is True
        plain_expanded = getattr(tc3.render(), "plain", str(tc3.render()))
        assert "● Read(README.md)" in plain_expanded
        assert "None" not in plain_expanded

        tc3.on_click()
        assert tc3._expanded is False
        plain_collapsed = getattr(tc3.render(), "plain", str(tc3.render()))
        assert "● Read(README.md)" in plain_collapsed


@pytest.mark.asyncio
async def test_textual_adapter_stream_turn_chronological_sequence() -> None:
    """Verify streaming turn mounts text -> tool call -> tool result -> post-tool text chronologically."""
    app = DummyApp()
    async with app.run_test():
        messages_list = app.query_one(MessageList)

        # Mock client.astream emitting stream events
        async def mock_astream(*args: Any, **kwargs: Any) -> AsyncGenerator[Tuple[None, str, Any], None]:
            # Step 1: Pre-tool thinking/text
            yield (
                None,
                "messages",
                (AIMessageChunk(content="Step 1: Let me check the README file."), {}),
            )

            # Step 2: Tool call invocation
            yield (
                None,
                "messages",
                (
                    AIMessageChunk(
                        content="",
                        tool_calls=[{"name": "read_file", "id": "call_abc", "args": {"path": "README.md"}}],
                    ),
                    {},
                ),
            )

            # Step 3: Tool execution completed result
            yield (
                None,
                "messages",
                (
                    ToolMessage(content="README contents here", tool_call_id="call_abc", name="read_file"),
                    {},
                ),
            )

            # Step 4: Post-tool text response
            yield (
                None,
                "messages",
                (AIMessageChunk(content="Step 2: Here is what I found in the README."), {}),
            )

        mock_client = MagicMock()
        mock_client.astream = mock_astream

        adapter = TextualAdapter(client=mock_client, assistant_id="dcoder", messages_widget=messages_list)

        await adapter.stream_turn("Check README", thread_id="thread-1")

        # Children mounted in MessageList
        children = list(messages_list.children)

        # We expect 3 distinct widgets mounted chronologically:
        # 1. AssistantMessage (Step 1)
        # 2. ToolCallMessage (read_file)
        # 3. AssistantMessage (Step 2 post-tool)
        assert len(children) == 3

        msg1, tool_msg, msg2 = children[0], children[1], children[2]

        assert isinstance(msg1, AssistantMessage)
        assert "".join(msg1._fragments) == "Step 1: Let me check the README file."

        assert isinstance(tool_msg, ToolCallMessage)
        assert tool_msg.tool_name == "read_file"
        assert tool_msg._call_id == "call_abc"
        assert tool_msg._status == "success"
        assert tool_msg._result == "README contents here"

        assert isinstance(msg2, AssistantMessage)
        assert "".join(msg2._fragments) == "Step 2: Here is what I found in the README."

        # Ensure msg1 and msg2 are two completely distinct AssistantMessage instances
        assert msg1 is not msg2


@pytest.mark.asyncio
async def test_single_stream_messaging_updates_ignored() -> None:
    """Verify mode=='updates' does not duplicate text or tool calls."""
    app = DummyApp()
    async with app.run_test():
        messages_list = app.query_one(MessageList)

        async def mock_astream(*args: Any, **kwargs: Any) -> AsyncGenerator[Tuple[None, str, Any], None]:
            # Message stream event
            yield (
                None,
                "messages",
                (AIMessageChunk(content="Hello!"), {}),
            )
            # Update stream event (should be ignored for text/tools, used only for interrupts)
            yield (
                None,
                "updates",
                {"agent": {"messages": [AIMessageChunk(content="Hello!")]}},
            )

        mock_client = MagicMock()
        mock_client.astream = mock_astream

        adapter = TextualAdapter(client=mock_client, assistant_id="dcoder", messages_widget=messages_list)

        await adapter.stream_turn("Hi", thread_id="thread-2")

        children = list(messages_list.children)
        # Only 1 AssistantMessage should be mounted, not duplicated
        assert len(children) == 1
        assert isinstance(children[0], AssistantMessage)
        assert "".join(children[0]._fragments) == "Hello!"
