"""Unit tests for /skills and /tools command handler."""

from unittest.mock import MagicMock
import pytest

from opscode.commands._base import CommandContext
from opscode.commands.core.skills import SkillsHandler


@pytest.mark.asyncio
async def test_skills_handler_tui_modal():
    """Verify /skills delegates to app._open_skills_viewer() in TUI mode."""
    handler = SkillsHandler()
    assert handler.name == "/skills"
    assert "/tools" in handler.aliases

    mock_app = MagicMock()
    mock_app._open_skills_viewer = MagicMock()

    ctx = CommandContext(
        app=mock_app,
        settings=MagicMock(),
        raw_command="/skills",
        args="",
    )

    res = await handler.execute(ctx)
    assert res.success
    assert res.mount_as_app_message is False
    assert mock_app._open_skills_viewer.called


@pytest.mark.asyncio
async def test_skills_handler_non_interactive_text():
    """Verify /skills falls back to text output when _open_skills_viewer is absent."""
    handler = SkillsHandler()
    mock_app = MagicMock(spec=["get_discovered_skills"])  # No _open_skills_viewer
    mock_app.get_discovered_skills.return_value = [
        {
            "name": "aws-ecs",
            "description": "AWS ECS management",
            "source": "user",
            "path": "/Users/test/.opscode/skills/aws-ecs/SKILL.md",
        }
    ]

    ctx = CommandContext(
        app=mock_app,
        settings=MagicMock(),
        raw_command="/skills",
        args="",
    )

    res = await handler.execute(ctx)
    assert res.success
    assert res.message is not None
    assert res.message is not None and "User Skills" in res.message
    assert res.message is not None and "aws-ecs" in res.message
    assert res.message is not None and "Location:" in res.message
    assert res.message is not None and "Purpose:" in res.message


@pytest.mark.asyncio
async def test_skills_handler_tools_alias_skips_modal():
    """Verify /tools alias does NOT push the modal (text output only)."""
    handler = SkillsHandler()
    mock_app = MagicMock()
    mock_app._open_skills_viewer = MagicMock()
    mock_app.get_discovered_skills.return_value = [
        {
            "name": "test-skill",
            "description": "Test desc",
            "source": "project",
            "path": "/tmp/skills/test/SKILL.md",
        }
    ]
    mock_app.get_active_tools.return_value = []
    mock_app.get_mcp_servers.return_value = []

    ctx = CommandContext(
        app=mock_app,
        settings=MagicMock(),
        raw_command="/tools",
        args="",
    )

    res = await handler.execute(ctx)
    assert res.success
    # /tools should NOT call _open_skills_viewer
    assert not mock_app._open_skills_viewer.called
    # Should produce text output
    assert res.message is not None


@pytest.mark.asyncio
async def test_skills_handler_empty_state():
    """Verify empty skills shows helpful directory hints."""
    handler = SkillsHandler()
    mock_app = MagicMock(spec=["get_discovered_skills"])  # No _open_skills_viewer
    mock_app.get_discovered_skills.return_value = []

    ctx = CommandContext(
        app=mock_app,
        settings=MagicMock(),
        raw_command="/skills",
        args="",
    )

    res = await handler.execute(ctx)
    assert res.success
    assert res.message is not None and "No skills found" in res.message
    assert res.message is not None and ".opscode/skills/" in res.message


@pytest.mark.asyncio
async def test_skills_handler_categorization():
    """Verify skills are grouped by source category."""
    handler = SkillsHandler()
    mock_app = MagicMock(spec=["get_discovered_skills"])  # No _open_skills_viewer
    mock_app.get_discovered_skills.return_value = [
        {"name": "proj-skill", "description": "Project skill", "source": "project", "path": "/proj/SKILL.md"},
        {"name": "usr-skill", "description": "User skill", "source": "user", "path": "/usr/SKILL.md"},
        {"name": "plug:skill", "description": "Plugin skill", "source": "plugin", "path": "/plug/SKILL.md"},
        {"name": "bi-skill", "description": "Built-in skill", "source": "built-in", "path": "/bi/SKILL.md"},
    ]

    ctx = CommandContext(
        app=mock_app,
        settings=MagicMock(),
        raw_command="/skills",
        args="",
    )

    res = await handler.execute(ctx)
    assert res.success
    assert res.message is not None and "Project Skills" in res.message
    assert res.message is not None and "User Skills" in res.message
    assert res.message is not None and "Plugin Skills" in res.message
    assert res.message is not None and "Built-in Skills" in res.message
