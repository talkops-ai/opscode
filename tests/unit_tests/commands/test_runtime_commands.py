"""Unit tests for runtime commands (/reload, /restart, /install, /update, /auto-update)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from opscode.commands._base import CommandContext
from opscode.commands._types import BypassTier, CommandCategory, SafetyLevel
from opscode.commands.power.runtime import (
    AutoUpdateHandler,
    InstallHandler,
    ReloadHandler,
    RestartHandler,
    UpdateHandler,
)
from opscode.ui.command_registry import get_command


# ── ReloadHandler Tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_reload_handler_metadata():
    handler = ReloadHandler()
    assert handler.name == "/reload"
    assert handler.category == CommandCategory.POWER
    assert handler.safety_level == SafetyLevel.LOW_RISK
    assert handler.bypass_tier == BypassTier.QUEUED


@pytest.mark.asyncio
async def test_reload_handler_app_delegation():
    app = MagicMock()
    app._invoke_reload = AsyncMock()
    ctx = CommandContext(app=app, raw_command="/reload")

    handler = ReloadHandler()
    res = await handler.execute(ctx)
    assert res.success
    assert not res.mount_as_app_message
    app._invoke_reload.assert_called_once_with(command="/reload")


@pytest.mark.asyncio
async def test_reload_handler_fallback():
    settings = MagicMock()
    settings.reload_from_environment.return_value = ["OPENAI_API_KEY"]
    ctx = CommandContext(app=None, settings=settings, raw_command="/reload")

    handler = ReloadHandler()
    with patch("opscode.commands.power.runtime._reload_dotenv"):
        res = await handler.execute(ctx)
    assert res.success
    assert res.mount_as_app_message
    assert res.message is not None and "1 changes" in res.message


# ── RestartHandler Tests ─────────────────────────────────


@pytest.mark.asyncio
async def test_restart_handler_metadata():
    handler = RestartHandler()
    assert handler.name == "/restart"
    assert handler.category == CommandCategory.POWER
    assert handler.safety_level == SafetyLevel.LOW_RISK
    assert handler.bypass_tier == BypassTier.ALWAYS


@pytest.mark.asyncio
async def test_restart_handler_app_delegation():
    app = MagicMock()
    app._handle_restart_command = AsyncMock()
    ctx = CommandContext(app=app, raw_command="/restart")

    handler = RestartHandler()
    res = await handler.execute(ctx)
    assert res.success
    assert not res.mount_as_app_message
    app._handle_restart_command.assert_called_once_with(command="/restart")


@pytest.mark.asyncio
async def test_restart_handler_fallback():
    ctx = CommandContext(app=None, raw_command="/restart")
    handler = RestartHandler()
    res = await handler.execute(ctx)
    assert res.success
    assert res.mount_as_app_message
    assert res.message is not None and "restart" in res.message.lower()


# ── InstallHandler Tests ─────────────────────────────────


@pytest.mark.asyncio
async def test_install_handler_metadata():
    handler = InstallHandler()
    assert handler.name == "/install"
    assert handler.category == CommandCategory.POWER
    assert handler.safety_level == SafetyLevel.LOW_RISK
    assert handler.bypass_tier == BypassTier.QUEUED


@pytest.mark.asyncio
async def test_install_handler_missing_args():
    handler = InstallHandler()
    ctx = CommandContext(app=None, raw_command="/install", args="")
    res = await handler.execute(ctx)
    assert not res.success
    assert res.message is not None and "Usage: /install" in res.message


@pytest.mark.asyncio
async def test_install_handler_app_delegation():
    app = MagicMock()
    app._handle_install_command = AsyncMock()
    ctx = CommandContext(app=app, raw_command="/install quickjs", args="quickjs")

    handler = InstallHandler()
    res = await handler.execute(ctx)
    assert res.success
    assert not res.mount_as_app_message
    app._handle_install_command.assert_called_once_with(command="/install quickjs")


@pytest.mark.asyncio
async def test_install_handler_fallback():
    ctx = CommandContext(app=None, raw_command="/install quickjs", args="quickjs")
    handler = InstallHandler()
    res = await handler.execute(ctx)
    assert res.success
    assert res.mount_as_app_message
    assert res.message is not None and "Installed `quickjs`" in res.message


# ── UpdateHandler Tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_update_handler_metadata():
    handler = UpdateHandler()
    assert handler.name == "/update"
    assert handler.category == CommandCategory.POWER
    assert handler.safety_level == SafetyLevel.LOW_RISK
    assert handler.bypass_tier == BypassTier.QUEUED


@pytest.mark.asyncio
async def test_update_handler_invalid_flags():
    handler = UpdateHandler()
    ctx = CommandContext(app=None, raw_command="/update --foo", args="--foo")
    res = await handler.execute(ctx)
    assert not res.success
    assert res.message is not None and "Unknown option" in res.message


@pytest.mark.asyncio
async def test_update_handler_app_delegation():
    app = MagicMock()
    app._handle_update_command = AsyncMock()
    ctx = CommandContext(app=app, raw_command="/update --deps", args="--deps")

    handler = UpdateHandler()
    res = await handler.execute(ctx)
    assert res.success
    assert not res.mount_as_app_message
    app._handle_update_command.assert_called_once_with(command="/update --deps")


@pytest.mark.asyncio
async def test_update_handler_fallback():
    ctx = CommandContext(app=None, raw_command="/update", args="")
    handler = UpdateHandler()

    with patch("opscode.commands.power.runtime._check_pypi_version", return_value="1.0.0"):
        with patch("opscode.__version__", "1.0.0", create=True):
            res = await handler.execute(ctx)
            assert res.success
            assert res.message is not None and "latest version" in res.message.lower()


# ── AutoUpdateHandler Tests ──────────────────────────────


@pytest.mark.asyncio
async def test_auto_update_handler_metadata():
    handler = AutoUpdateHandler()
    assert handler.name == "/auto-update"
    assert handler.category == CommandCategory.POWER
    assert handler.safety_level == SafetyLevel.LOW_RISK
    assert handler.bypass_tier == BypassTier.SIDE_EFFECT_FREE


@pytest.mark.asyncio
async def test_auto_update_toggle_on():
    settings = MagicMock()
    settings.auto_update = False
    ctx = CommandContext(app=None, settings=settings, raw_command="/auto-update on", args="on")

    handler = AutoUpdateHandler()
    res = await handler.execute(ctx)
    assert res.success
    assert settings.auto_update is True
    assert res.message is not None and "enabled" in res.message


@pytest.mark.asyncio
async def test_auto_update_toggle_off():
    settings = MagicMock()
    settings.auto_update = True
    ctx = CommandContext(app=None, settings=settings, raw_command="/auto-update off", args="off")

    handler = AutoUpdateHandler()
    res = await handler.execute(ctx)
    assert res.success
    assert settings.auto_update is False
    assert res.message is not None and "disabled" in res.message


@pytest.mark.asyncio
async def test_auto_update_status():
    settings = MagicMock()
    settings.auto_update = True
    ctx = CommandContext(app=None, settings=settings, raw_command="/auto-update status", args="status")

    handler = AutoUpdateHandler()
    res = await handler.execute(ctx)
    assert res.success
    assert settings.auto_update is True
    assert res.message is not None and "enabled" in res.message


# ── Command Registry Verification ────────────────────────


def test_command_registry_runtime_entries():
    reload_cmd = get_command("/reload")
    assert reload_cmd is not None
    assert reload_cmd.bypass_tier == BypassTier.QUEUED

    restart_cmd = get_command("/restart")
    assert restart_cmd is not None
    assert restart_cmd.bypass_tier == BypassTier.ALWAYS

    install_cmd = get_command("/install")
    assert install_cmd is not None
    assert install_cmd.bypass_tier == BypassTier.QUEUED
    assert install_cmd.argument_hint == "<extra|package> [--package] [--force]"

    update_cmd = get_command("/update")
    assert update_cmd is not None
    assert update_cmd.bypass_tier == BypassTier.QUEUED
    assert update_cmd.argument_hint == "[--deps] [--prerelease]"

    autoupdate_cmd = get_command("/auto-update")
    assert autoupdate_cmd is not None
    assert autoupdate_cmd.bypass_tier == BypassTier.SIDE_EFFECT_FREE
    assert autoupdate_cmd.argument_hint == "[on|off|status]"
