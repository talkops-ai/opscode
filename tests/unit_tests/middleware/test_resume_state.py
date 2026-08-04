"""Unit tests for ResumeStateMiddleware — state persistence after model calls."""

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.messages.ai import UsageMetadata

from dcoder.middleware.resume_state import (
    ResumeState,
    ResumeStateMiddleware,
    _extract_context_tokens,
    coerce_goal_proposal_kind,
    coerce_goal_status,
)


class TestExtractContextTokens:
    """Tests for _extract_context_tokens helper."""

    def test_returns_sum_of_input_and_output(self):
        msg = AIMessage(content="hello")
        msg.usage_metadata = UsageMetadata({"input_tokens": 100, "output_tokens": 50, "total_tokens": 150})
        assert _extract_context_tokens(msg) == 150

    def test_returns_total_when_split_unavailable(self):
        msg = AIMessage(content="hello")
        msg.usage_metadata = UsageMetadata({"input_tokens": 0, "output_tokens": 0, "total_tokens": 200})
        assert _extract_context_tokens(msg) == 200

    def test_returns_none_when_no_usage(self):
        msg = AIMessage(content="hello")
        assert _extract_context_tokens(msg) is None

    def test_returns_none_when_all_zeros(self):
        msg = AIMessage(content="hello")
        msg.usage_metadata = UsageMetadata({"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
        assert _extract_context_tokens(msg) is None

    def test_prefers_split_over_total(self):
        msg = AIMessage(content="hello")
        msg.usage_metadata = UsageMetadata({"input_tokens": 100, "output_tokens": 50, "total_tokens": 999})
        assert _extract_context_tokens(msg) == 150


class TestCoerceGoalStatus:
    """Tests for coerce_goal_status."""

    def test_valid_statuses(self):
        assert coerce_goal_status("active") == "active"
        assert coerce_goal_status("paused") == "paused"
        assert coerce_goal_status("blocked") == "blocked"
        assert coerce_goal_status("complete") == "complete"

    def test_invalid_values(self):
        assert coerce_goal_status("unknown") is None
        assert coerce_goal_status(42) is None
        assert coerce_goal_status(None) is None
        assert coerce_goal_status("") is None


class TestCoerceGoalProposalKind:
    """Tests for coerce_goal_proposal_kind."""

    def test_valid_kinds(self):
        assert coerce_goal_proposal_kind("create") == "create"
        assert coerce_goal_proposal_kind("amend") == "amend"

    def test_invalid_values(self):
        assert coerce_goal_proposal_kind("delete") is None
        assert coerce_goal_proposal_kind(123) is None
        assert coerce_goal_proposal_kind(None) is None


class TestResumeStateMiddleware:
    """Tests for the after_model hook."""

    def test_after_model_extracts_tokens(self):
        middleware = ResumeStateMiddleware()
        ai_msg = AIMessage(content="response")
        ai_msg.usage_metadata = UsageMetadata({"input_tokens": 500, "output_tokens": 100, "total_tokens": 600})

        state = cast(ResumeState, {"messages": [HumanMessage(content="hi"), ai_msg]})
        runtime = cast(Any, MagicMock())

        result = middleware.after_model(state, runtime)
        assert result is not None
        assert result["_context_tokens"] == 600

    def test_after_model_returns_none_when_no_ai_message(self):
        middleware = ResumeStateMiddleware()
        state = cast(ResumeState, {"messages": [HumanMessage(content="hi")]})
        runtime = cast(Any, MagicMock())

        result = middleware.after_model(state, runtime)
        assert result is None

    def test_after_model_returns_none_when_no_usage(self):
        middleware = ResumeStateMiddleware()
        ai_msg = AIMessage(content="response")
        # No usage_metadata

        state = cast(ResumeState, {"messages": [ai_msg]})
        runtime = cast(Any, MagicMock())

        result = middleware.after_model(state, runtime)
        assert result is None

    def test_after_model_uses_last_ai_message(self):
        middleware = ResumeStateMiddleware()
        old_msg = AIMessage(content="old")
        old_msg.usage_metadata = UsageMetadata({"input_tokens": 100, "output_tokens": 10, "total_tokens": 110})
        new_msg = AIMessage(content="new")
        new_msg.usage_metadata = UsageMetadata({"input_tokens": 500, "output_tokens": 200, "total_tokens": 700})

        state = cast(ResumeState, {"messages": [old_msg, HumanMessage(content="next"), new_msg]})
        runtime = cast(Any, MagicMock())

        result = middleware.after_model(state, runtime)
        assert result is not None
        assert result["_context_tokens"] == 700

    def test_after_model_empty_messages(self):
        middleware = ResumeStateMiddleware()
        state = cast(ResumeState, {"messages": []})
        runtime = cast(Any, MagicMock())

        result = middleware.after_model(state, runtime)
        assert result is None
