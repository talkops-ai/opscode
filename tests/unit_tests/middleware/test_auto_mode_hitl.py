"""Unit tests for AutoModeHITLMiddleware — classifier-backed approval policy."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from dcoder.middleware.auto_mode import (
    AutoModeHITLMiddleware,
    USER_PROMPT_METADATA_KEY,
    user_prompt_metadata,
)


class TestUserPromptMetadata:
    """Tests for the user_prompt_metadata helper."""

    def test_basic_metadata(self):
        meta = user_prompt_metadata("hello world")
        assert meta["literal_user_text"] == "hello world"
        assert meta["referenced_paths"] == []
        assert "turn_id" in meta

    def test_with_paths_and_turn_id(self):
        meta = user_prompt_metadata(
            "fix this",
            referenced_paths=["/src/foo.py", "/src/bar.py"],
            turn_id="turn-42",
        )
        assert meta["referenced_paths"] == ["/src/foo.py", "/src/bar.py"]
        assert meta["turn_id"] == "turn-42"

    def test_auto_generates_turn_id(self):
        meta = user_prompt_metadata("test")
        assert meta["turn_id"] is not None
        assert len(meta["turn_id"]) > 0


class TestAutoModeHITLMiddleware:
    """Tests for the AutoModeHITLMiddleware."""

    def test_init_default_empty_interrupt_on(self):
        middleware = AutoModeHITLMiddleware()
        assert middleware.interrupt_on == {}

    def test_init_with_interrupt_on(self):
        from typing import Any, cast
        interrupt_config: dict[str, Any] = {"write_file": True, "delete": True}
        middleware = AutoModeHITLMiddleware(interrupt_on=interrupt_config)
        assert "write_file" in middleware.interrupt_on
        assert "delete" in middleware.interrupt_on

    def test_init_with_shell_allow_list(self):
        middleware = AutoModeHITLMiddleware(
            interrupt_on={"execute": True},
            shell_allow_list=["ls", "cat"],
        )
        assert middleware._shell_allow_list == ["ls", "cat"]

    @pytest.mark.asyncio
    async def test_awrap_model_call_no_tool_calls(self):
        """When the AI response has no tool calls, pass through with decision=None."""
        middleware = AutoModeHITLMiddleware(interrupt_on={"write_file": True})

        ai_msg = AIMessage(content="Just a text response")

        mock_response = MagicMock()
        mock_response.result = [ai_msg]

        handler = AsyncMock(return_value=mock_response)
        request = MagicMock()

        result = await middleware.awrap_model_call(request, handler)
        handler.assert_awaited_once_with(request)
        # Should return ExtendedModelResponse with decision plan cleared
        from typing import cast, Any
        ext_result = cast(Any, result)
        assert ext_result.command.update.get("_auto_decision_plan") is None

    @pytest.mark.asyncio
    async def test_awrap_model_call_with_non_gated_tool_calls(self):
        """Tool calls not in interrupt_on should pass through normally."""
        middleware = AutoModeHITLMiddleware(interrupt_on={"write_file": True})

        ai_msg = AIMessage(content="")
        ai_msg.tool_calls = [{"name": "read_file", "args": {"path": "/foo"}, "id": "tc1"}]

        mock_response = MagicMock()
        mock_response.result = [ai_msg]

        handler = AsyncMock(return_value=mock_response)
        request = MagicMock()

        result = await middleware.awrap_model_call(request, handler)
        # Non-gated calls should return the original response
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_awrap_model_call_with_gated_tool_calls(self):
        """Tool calls IN interrupt_on should produce an extended response with decision plan."""
        middleware = AutoModeHITLMiddleware(interrupt_on={"write_file": True})

        ai_msg = AIMessage(content="")
        ai_msg.tool_calls = [
            {"name": "write_file", "args": {"path": "/foo"}, "id": "tc1"},
            {"name": "read_file", "args": {"path": "/bar"}, "id": "tc2"},
        ]

        mock_response = MagicMock()
        mock_response.result = [ai_msg]

        handler = AsyncMock(return_value=mock_response)
        request = MagicMock()

        result = await middleware.awrap_model_call(request, handler)
        # Should return ExtendedModelResponse
        assert hasattr(result, "command")
        from typing import cast, Any
        ext_result = cast(Any, result)
        decision_plan = ext_result.command.update.get("_auto_decision_plan")
        assert decision_plan is not None
        assert decision_plan["gated_calls_count"] == 1
