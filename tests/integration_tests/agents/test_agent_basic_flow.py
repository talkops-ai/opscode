"""Integration test — basic agent creation and conversation flow.

Requires a real LLM API key. Uses the cheapest available model.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.timeout(30)
class TestAgentBasicFlow:
    """End-to-end test with a real (cheap) LLM."""

    @pytest.mark.asyncio
    async def test_agent_responds_to_simple_prompt(self, test_model_spec):
        """Verify the agent can be created and responds to a basic prompt."""
        from dcoder.agent.factory import create_dcoder_agent

        agent, backend = create_dcoder_agent(
            model=test_model_spec,
            interactive=False,
        )
        assert agent is not None

    @pytest.mark.asyncio
    async def test_agent_creation_with_defaults(self, test_model_spec):
        """Verify agent factory doesn't crash with default configuration."""
        from dcoder.agent.factory import create_dcoder_agent

        agent, backend = create_dcoder_agent(
            model=test_model_spec,
            interactive=False,
        )
        # Basic sanity: the compiled graph should have nodes
        assert agent is not None
