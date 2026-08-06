"""Unit tests for CostTrackingMiddleware, _SessionCostRecorder, and cost estimation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from langgraph.types import Overwrite

from dcoder.middleware.cost_tracking import (
    CostState,
    CostTrackingMiddleware,
    _SessionCostRecorder,
    _checkpoint_scope,
    _owning_checkpoint_scope,
    _parent_checkpoint_scope,
    estimate_cost,
    pricing_data_available,
    resolve_message_model,
)


class TestCostEstimation:
    """Test token usage cost calculation and provider resolution."""

    def test_estimate_cost_valid_metadata(self) -> None:
        usage = {
            "input_tokens": 100,
            "output_tokens": 50,
            "input_token_details": {"cache_read": 20},
        }
        cost = estimate_cost(usage, model_name="gpt-4o", provider="openai")
        # genai-prices gives a positive float estimate for gpt-4o when available
        if pricing_data_available():
            assert cost is not None
            assert cost > 0.0

    def test_estimate_cost_empty_usage(self) -> None:
        assert estimate_cost(None, model_name="gpt-4o") is None
        assert estimate_cost({}, model_name="gpt-4o") is None

    def test_estimate_cost_unpriceable_provider(self) -> None:
        usage = {"input_tokens": 100, "output_tokens": 50}
        assert estimate_cost(usage, model_name="codex", provider="openai_codex") is None

    def test_resolve_message_model_fallback(self) -> None:
        msg = AIMessage(content="Hello", response_metadata={"model_name": "gpt-4o-mini"})
        model, provider = resolve_message_model(
            msg, fallback_model="gpt-4o", fallback_provider="openai"
        )
        assert model == "gpt-4o-mini"
        assert provider == "openai"


class TestCheckpointScopeHelpers:
    """Test graph namespace parent and owner scope computation."""

    def test_parent_checkpoint_scope(self) -> None:
        assert _parent_checkpoint_scope("") == ""
        assert _parent_checkpoint_scope("agent|node_1") == "agent"
        assert _parent_checkpoint_scope("agent|subagent|node_2") == "agent|subagent"

    def test_owning_checkpoint_scope(self) -> None:
        assert _owning_checkpoint_scope("") == ""
        assert _owning_checkpoint_scope("parent|1|subagent|2") == "parent"


class TestCostTrackingMiddleware:
    """Test CostTrackingMiddleware lifecycle hooks."""

    def test_before_agent_main_vs_nested(self) -> None:
        main_mw = CostTrackingMiddleware(nested=False)
        nested_mw = CostTrackingMiddleware(nested=True)

        state: CostState = {"messages": []}
        runtime = MagicMock()

        assert main_mw.before_agent(state, runtime) is None

        nested_update = nested_mw.before_agent(state, runtime)
        assert nested_update is not None
        assert isinstance(nested_update.get("_session_cost_usd"), Overwrite)
        assert nested_update["_session_cost_usd"].value == 0.0

    def test_after_model_no_records_returns_none(self) -> None:
        mw = CostTrackingMiddleware(nested=False)
        state: CostState = {"messages": []}
        runtime = MagicMock()
        execution_info = MagicMock()
        execution_info.thread_id = "test-thread-1"
        execution_info.checkpoint_ns = "main|node"
        runtime.execution_info = execution_info

        update = mw.after_model(state, runtime)
        assert update is None

    def test_after_model_prices_ai_message_with_usage(self) -> None:
        mw = CostTrackingMiddleware(nested=False)
        msg = AIMessage(
            content="Done",
            id="msg-1",
            response_metadata={"model_name": "gpt-4o", "provider": "openai"},
            usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )
        state: CostState = {"messages": [msg], "_model_spec": "openai:gpt-4o"}
        runtime = MagicMock()
        execution_info = MagicMock()
        execution_info.thread_id = "test-thread-2"
        execution_info.checkpoint_ns = "main|node"
        runtime.execution_info = execution_info
        runtime.stream_writer = MagicMock()

        update = mw.after_model(state, runtime)
        if pricing_data_available():
            assert update is not None
            assert "_session_cost_usd" in update
            assert update["_session_cost_usd"] > 0.0
            runtime.stream_writer.assert_called_once()


class TestSessionCostRecorder:
    """Test _SessionCostRecorder lifecycle and record buffering."""

    def test_recorder_drain_and_restore(self) -> None:
        recorder = _SessionCostRecorder()
        thread_id = "test-thread-rec"

        gen = ChatGeneration(
            text="Hi",
            message=AIMessage(
                content="Hi",
                id="msg-rec-1",
                usage_metadata={"input_tokens": 50, "output_tokens": 10, "total_tokens": 60},
            ),
        )
        llm_result = LLMResult(generations=[[gen]])

        import uuid

        run_id = uuid.uuid4()
        recorder.on_chat_model_start(
            {}, [], run_id=run_id, metadata={"thread_id": thread_id}
        )
        recorder.on_llm_end(llm_result, run_id=run_id)

        records = recorder.drain(thread_id)
        assert len(records) == 1
        assert records[0].message_id == "msg-rec-1"

        # Drain again should be empty
        assert len(recorder.drain(thread_id)) == 0

        # Restore records
        recorder.restore(thread_id, records)
        restored = recorder.drain(thread_id)
        assert len(restored) == 1
        assert restored[0].message_id == "msg-rec-1"
