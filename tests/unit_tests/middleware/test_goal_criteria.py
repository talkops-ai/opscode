"""Unit tests for GoalCriteriaMiddleware — types, budget middleware, state management, and agent creation."""

from unittest.mock import MagicMock

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from opscode.middleware.goal_criteria import (
    GoalAmendRequest,
    GoalCreateRequest,
    GoalCriteriaMiddleware,
    GoalProposal,
    _REPOSITORY_RECURSION_LIMIT,
    _STRUCTURED_OUTPUT_TOOL_NAME,
    _WEB_SEARCH_CALL_LIMIT,
    create_goal_criteria_agent,
    create_goal_criteria_fallback_agent,
)


class TestGoalProposalType:
    """Tests for GoalProposal TypedDict structure."""

    def test_valid_proposal(self):
        proposal: GoalProposal = {
            "objective": "Deploy a VPC with 3 subnets",
            "criteria": "1. VPC created\n2. 3 subnets created",
        }
        assert proposal["objective"] == "Deploy a VPC with 3 subnets"
        assert "1. VPC created" in proposal["criteria"]

    def test_proposal_keys(self):
        proposal: GoalProposal = {"objective": "test", "criteria": "test"}
        assert set(proposal.keys()) == {"objective", "criteria"}


class TestBudgetConstants:
    """Verify budget constants are sensible."""

    def test_repository_recursion_limit_positive(self):
        assert _REPOSITORY_RECURSION_LIMIT > 0
        assert _REPOSITORY_RECURSION_LIMIT >= 4  # At least 2x tool calls + 2

    def test_web_search_call_limit_positive(self):
        assert _WEB_SEARCH_CALL_LIMIT > 0
        assert _WEB_SEARCH_CALL_LIMIT <= 10  # Shouldn't be excessive

    def test_structured_output_tool_name(self):
        assert _STRUCTURED_OUTPUT_TOOL_NAME == "GoalProposal"


class TestGoalCriteriaRequestTypes:
    """Tests for request type structures."""

    def test_create_request_structure(self):
        req: GoalCreateRequest = {
            "kind": "create",
            "request_id": "req-001",
            "objective": "Deploy infrastructure",
        }
        assert req["kind"] == "create"
        assert req["request_id"] == "req-001"

    def test_amend_request_structure(self):
        req: GoalAmendRequest = {
            "kind": "amend",
            "request_id": "req-002",
            "objective": "Deploy infrastructure",
            "criteria": "1. VPC created",
            "feedback": "Add subnet check",
        }
        assert req["kind"] == "amend"
        assert req["feedback"] == "Add subnet check"

    def test_create_request_with_rejection_retry(self):
        req: GoalCreateRequest = {
            "kind": "create",
            "request_id": "req-003",
            "objective": "Deploy VPC",
            "feedback": "Too vague, add specifics",
            "previous_criteria": "1. VPC exists",
        }
        assert req["feedback"] == "Too vague, add specifics"
        assert req["previous_criteria"] == "1. VPC exists"


class TestGoalCriteriaAgentCreation:
    """Tests for create_goal_criteria_agent and create_goal_criteria_fallback_agent."""

    def test_create_goal_criteria_agent_with_mock_model(self):
        from deepagents.backends import StateBackend
        model = GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))
        backend = StateBackend()
        agent = create_goal_criteria_agent(
            model=model,
            repository_backend=backend,
            repository_root="/tmp/repo",
            context_tools=[],
        )
        assert agent is not None

    def test_create_goal_criteria_agent_conflicting_tools_raises(self):
        model = GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))

        @tool("GoalProposal")
        def conflicting_tool() -> str:
            """Conflict with reserved name."""
            return "conflict"

        with pytest.raises(ValueError, match="Context tool names conflict"):
            create_goal_criteria_agent(
                model=model,
                repository_backend=None,
                repository_root="/tmp",
                context_tools=[conflicting_tool],
            )

    def test_create_goal_criteria_fallback_agent(self):
        model = GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))
        fallback_agent = create_goal_criteria_fallback_agent(model=model)
        assert fallback_agent is not None


class TestGoalCriteriaMiddlewareExecution:
    """Tests for GoalCriteriaMiddleware state lifecycle."""

    def test_middleware_instantiation(self):
        criteria_agent = MagicMock()
        fallback_agent = MagicMock()
        middleware = GoalCriteriaMiddleware(
            criteria_agent=criteria_agent,
            fallback_agent=fallback_agent,
        )
        assert middleware._criteria_agent is criteria_agent
        assert middleware._fallback_agent is fallback_agent

    def test_before_agent_no_request_passthrough(self):
        from typing import Any, cast
        middleware = GoalCriteriaMiddleware(
            criteria_agent=MagicMock(),
            fallback_agent=MagicMock(),
        )
        state = cast(Any, {"messages": []})
        runtime = MagicMock()
        result = middleware.before_agent(state, runtime)
        assert result is None
