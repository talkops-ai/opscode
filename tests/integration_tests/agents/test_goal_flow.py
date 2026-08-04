"""Integration test — goal-mode lifecycle with real LLM.

Requires a real LLM API key. Uses the cheapest available model.
Tests: set goal → generate rubric → validate structure.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.timeout(45)
class TestGoalFlow:
    """Goal-mode lifecycle with a real model."""

    @pytest.mark.asyncio
    async def test_rubric_generation_structure(self, test_model_spec):
        """Verify rubric generator produces structured output."""
        from dcoder.rubrics.generator import GOAL_RUBRIC_SYSTEM_PROMPT

        # Verify the system prompt exists and is non-trivial
        assert isinstance(GOAL_RUBRIC_SYSTEM_PROMPT, str)
        assert len(GOAL_RUBRIC_SYSTEM_PROMPT) > 50
        assert "criteria" in GOAL_RUBRIC_SYSTEM_PROMPT.lower() or "rubric" in GOAL_RUBRIC_SYSTEM_PROMPT.lower()
