"""Integration tests for app.py wiring and legacy command fallback."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from dcoder.commands._base import BaseCommandHandler, CommandContext, CommandResult
from dcoder.commands._types import CommandCategory, SafetyLevel
from dcoder.ui.app import DCoderApp


class RegisteredTestCommand(BaseCommandHandler):
    @property
    def name(self) -> str:
        return "/testcmd"

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.CORE

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.READ_ONLY

    async def execute(self, ctx: CommandContext) -> CommandResult:
        return CommandResult(success=True, message="Test command router dispatch succeeded!")


@pytest.fixture
def dummy_app():
    app = DCoderApp()
    app._mount_message = AsyncMock()  # type: ignore
    return app


@pytest.mark.asyncio
async def test_app_router_dispatch(dummy_app):
    """Verify app._handle_command routes registered commands through CommandRouter."""
    handler = RegisteredTestCommand()
    dummy_app._command_router.register(handler)

    await dummy_app._handle_command("/testcmd")
    dummy_app._mount_message.assert_called_once()
    msg = dummy_app._mount_message.call_args[0][0]
    content_obj = getattr(msg, "_Static__content", None)
    text_content = getattr(content_obj, "markup", str(msg))
    assert "Test command router dispatch succeeded!" in text_content


@pytest.mark.asyncio
async def test_app_legacy_fallback(dummy_app):
    """Verify unregistered commands fall back to legacy inline handling in app.py."""
    dummy_app._show_agent_selector = AsyncMock()
    # /agents is an unmigrated inline command in app.py (Phase 3)
    await dummy_app._handle_command("/agents")
    dummy_app._show_agent_selector.assert_called_once()
