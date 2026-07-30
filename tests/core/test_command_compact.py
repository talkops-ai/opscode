"""Unit tests for CompactHandler (/compact, /offload)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from dcoder.commands._base import CommandContext
from dcoder.commands.core.compact import CompactHandler


@pytest.mark.asyncio
async def test_compact_requires_minimum_messages():
    """Verify /compact fails if message count is less than 4."""
    mock_app = MagicMock()
    mock_app._agent_running = False
    mock_app.get_thread_messages.return_value = ["msg1", "msg2"]

    ctx = CommandContext(app=mock_app, raw_command="/compact")
    handler = CompactHandler()

    res = await handler.execute(ctx)
    assert res.success is False
    assert "Not enough messages" in res.message


@pytest.mark.asyncio
async def test_compact_agent_running_error():
    """Verify /compact fails when agent is actively running."""
    mock_app = MagicMock()
    mock_app._agent_running = True

    ctx = CommandContext(app=mock_app, raw_command="/compact")
    handler = CompactHandler()

    res = await handler.execute(ctx)
    assert res.success is False
    assert "Cannot compact while agent is running" in res.message


@pytest.mark.asyncio
async def test_compact_success_token_savings():
    """Verify /compact calculates before/after tokens and executes compaction."""
    mock_app = MagicMock()
    mock_app._agent_running = False
    mock_app._agent_thread_id = "thread-123"
    mock_app.get_thread_messages.return_value = ["message 1", "message 2", "message 3", "message 4", "message 5"]
    mock_app.invoke_compact_conversation = AsyncMock()

    ctx = CommandContext(app=mock_app, raw_command="/compact")
    handler = CompactHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert "Conversation Compacted" in res.message
    assert "Freed:" in res.message
