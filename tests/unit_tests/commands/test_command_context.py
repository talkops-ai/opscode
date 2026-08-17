"""Unit tests for ContextHandler (/context)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from opscode.commands._base import CommandContext
from opscode.commands.core.context import ContextHandler


@pytest.mark.asyncio
async def test_context_handler_token_and_resource_display():
    """Verify /context displays token counts, limit percentage, and resource counts."""
    mock_app = MagicMock()
    mock_app.get_context_tokens.return_value = 25000
    mock_app.get_conversation_token_count = AsyncMock(return_value=15000)
    mock_app.get_active_tools.return_value = ["tool1", "tool2"]
    mock_app.get_mcp_servers.return_value = ["mcp1"]
    mock_app.get_discovered_skills.return_value = ["skill1"]

    mock_settings = MagicMock()
    mock_settings.model_context_limit = 100000
    mock_settings.model_name = "claude-3-5-sonnet"
    mock_settings.cloud_context = None
    mock_settings.kube_context = None

    ctx = CommandContext(app=mock_app, settings=mock_settings, raw_command="/context")
    handler = ContextHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "25,000 / 100,000 tokens (25.0%)" in res.message
    assert res.message is not None and "2 tools · 1 MCP servers · 1 skills" in res.message


@pytest.mark.asyncio
async def test_context_handler_infrastructure_context():
    """Verify /context displays cloud and k8s infrastructure context when set."""
    mock_app = MagicMock()
    mock_app.get_context_tokens.return_value = 5000
    mock_app.get_conversation_token_count = AsyncMock(return_value=None)
    mock_app.get_active_tools.return_value = []
    mock_app.get_mcp_servers.return_value = []
    mock_app.get_discovered_skills.return_value = []

    mock_settings = MagicMock()
    mock_settings.model_context_limit = None
    mock_settings.model_name = "gpt-4o"
    mock_settings.cloud_context = "aws:us-east-1"
    mock_settings.kube_context = "prod-cluster"

    ctx = CommandContext(app=mock_app, settings=mock_settings, raw_command="/context")
    handler = ContextHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "Infrastructure Context:" in res.message
    assert res.message is not None and "aws:us-east-1" in res.message
    assert res.message is not None and "prod-cluster" in res.message
