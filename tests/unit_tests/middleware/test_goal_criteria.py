"""Unit tests for GoalCriteriaMiddleware — types, budget middleware, and state management."""

import pytest

from dcoder.middleware.goal_criteria import (
    GoalProposal,
    _REPOSITORY_RECURSION_LIMIT,
    _STRUCTURED_OUTPUT_TOOL_NAME,
    _WEB_SEARCH_CALL_LIMIT,
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
        from dcoder.middleware.goal_criteria import GoalCreateRequest

        req: GoalCreateRequest = {
            "kind": "create",
            "request_id": "req-001",
            "objective": "Deploy infrastructure",
        }
        assert req["kind"] == "create"
        assert req["request_id"] == "req-001"

    def test_amend_request_structure(self):
        from dcoder.middleware.goal_criteria import GoalAmendRequest

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
        from dcoder.middleware.goal_criteria import GoalCreateRequest

        req: GoalCreateRequest = {
            "kind": "create",
            "request_id": "req-003",
            "objective": "Deploy VPC",
            "feedback": "Too vague, add specifics",
            "previous_criteria": "1. VPC exists",
        }
        assert req["feedback"] == "Too vague, add specifics"
        assert req["previous_criteria"] == "1. VPC exists"
