"""Unit tests for Phase 3 command handlers."""

from unittest.mock import MagicMock, AsyncMock, PropertyMock, patch
from pathlib import Path

import pytest

from dcoder.commands._base import CommandContext


# ── Helper ──────────────────────────────────────────────

def _make_ctx(args: str = "", raw: str = "", **overrides):
    mock_settings = MagicMock()
    mock_settings.config_path = Path.home() / ".dcoder" / "config.toml"
    mock_settings.to_display_dict.return_value = {"model_name": "claude-3", "reasoning_effort": "high"}
    mock_settings.project_root = Path("/tmp/project")
    return CommandContext(
        app=overrides.get("app", MagicMock()),
        settings=overrides.get("settings", mock_settings),
        raw_command=raw or f"/{args.split()[0] if args else 'test'}",
        args=args,
        **{k: v for k, v in overrides.items() if k not in ("app", "settings")},
    )


# ── /config ─────────────────────────────────────────────

class TestConfigHandler:
    @pytest.mark.asyncio
    async def test_show_pushes_screen_in_app(self):
        from dcoder.commands.core.config_cmd import ConfigHandler
        mock_app = MagicMock()
        ctx = _make_ctx(args="", raw="/config", app=mock_app)
        res = await ConfigHandler().execute(ctx)
        assert res.success
        mock_app.push_screen.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_cli_displays_settings(self):
        from dcoder.commands.core.config_cmd import ConfigHandler
        ctx = _make_ctx(args="", raw="/config", app=None)
        res = await ConfigHandler().execute(ctx)
        assert res.success
        assert res.message is not None and "Configuration" in res.message

    @pytest.mark.asyncio
    async def test_path_shows_location(self):
        from dcoder.commands.core.config_cmd import ConfigHandler
        ctx = _make_ctx(args="path", raw="/config path")
        res = await ConfigHandler().execute(ctx)
        assert res.success
        assert res.message is not None and "config.toml" in res.message

    @pytest.mark.asyncio
    async def test_masks_secrets(self):
        from dcoder.commands.core.config_cmd import ConfigHandler
        assert "..." in ConfigHandler._mask_secret("api_key", "sk-1234567890abcdef")

    @pytest.mark.asyncio
    async def test_set_valid_key(self):
        from dcoder.commands.core.config_cmd import ConfigHandler
        mock_settings = MagicMock()
        mock_settings.set_field.return_value = (True, "Set key = value")
        ctx = _make_ctx(args="set reasoning_effort high", raw="/config set reasoning_effort high",
                        settings=mock_settings)
        res = await ConfigHandler().execute(ctx)
        assert res.success

    @pytest.mark.asyncio
    async def test_reset_valid_key(self):
        from dcoder.commands.core.config_cmd import ConfigHandler
        mock_settings = MagicMock()
        mock_settings.reset_field.return_value = (True, "Reset key to default")
        ctx = _make_ctx(args="reset reasoning_effort", raw="/config reset reasoning_effort",
                        settings=mock_settings)
        res = await ConfigHandler().execute(ctx)
        assert res.success
        assert res.message is not None and "Reset" in res.message

    @pytest.mark.asyncio
    async def test_invalid_subcommand(self):
        from dcoder.commands.core.config_cmd import ConfigHandler
        ctx = _make_ctx(args="garbage", raw="/config garbage")
        res = await ConfigHandler().execute(ctx)
        assert not res.success
        assert res.message is not None and "Usage" in res.message


# ── /doctor ─────────────────────────────────────────────

class TestDoctorHandler:
    @pytest.mark.asyncio
    async def test_reports_all_sections(self):
        from dcoder.commands.core.doctor import DoctorHandler
        mock_app = MagicMock()
        mock_app.get_mcp_servers.return_value = []
        ctx = _make_ctx(raw="/doctor", app=mock_app)
        res = await DoctorHandler().execute(ctx)
        assert res.success
        assert res.message is not None and "Doctor" in res.message
        assert res.message is not None and "Diagnostics" in res.message
        assert res.message is not None and "API Keys" in res.message
        assert res.message is not None and "DevOps Tools" in res.message

    @pytest.mark.asyncio
    async def test_detects_missing_keys(self):
        from dcoder.commands.core.doctor import DoctorHandler
        mock_settings = MagicMock()
        mock_settings.openai_api_key = None
        mock_settings.anthropic_api_key = None
        mock_settings.google_api_key = None
        mock_settings.groq_api_key = None
        mock_settings.deepseek_api_key = None
        mock_settings.tavily_api_key = None
        mock_app = MagicMock()
        mock_app.get_mcp_servers.return_value = []
        ctx = _make_ctx(raw="/doctor", app=mock_app, settings=mock_settings)
        res = await DoctorHandler().execute(ctx)
        assert res.message is not None and "NO PROVIDERS CONFIGURED" in res.message

    @pytest.mark.asyncio
    async def test_doctor_mcp_connected(self):
        from dcoder.commands.core.doctor import DoctorHandler
        mock_app = MagicMock()
        from dcoder.mcp.mcp_info import MCPServerInfo, MCPToolInfo
        mock_app.get_mcp_servers.return_value = [
            MCPServerInfo(
                name="alphavantage",
                transport="stdio",
                tools=tuple(MCPToolInfo(name=f"t{i}") for i in range(3)),
                status="ok",
            )
        ]
        ctx = _make_ctx(raw="/doctor", app=mock_app)
        res = await DoctorHandler().execute(ctx)
        assert res.success
        assert res.message is not None and "alphavantage" in res.message
        assert res.message is not None and "connected (3 tools)" in res.message


# ── /login ──────────────────────────────────────────────

class TestLoginHandler:
    @pytest.mark.asyncio
    async def test_pushes_auth_manager(self):
        from dcoder.commands.core.auth import LoginHandler
        mock_app = MagicMock()
        ctx = _make_ctx(raw="/login", app=mock_app)
        res = await LoginHandler().execute(ctx)
        assert res.success
        mock_app.push_screen.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_with_initial_provider(self):
        from dcoder.commands.core.auth import LoginHandler
        mock_app = MagicMock()
        ctx = _make_ctx(args="anthropic", raw="/login anthropic", app=mock_app)
        res = await LoginHandler().execute(ctx)
        assert res.success
        screen_pushed = mock_app.push_screen.call_args[0][0]
        assert getattr(screen_pushed, "_initial_provider", None) == "anthropic"


# ── /logout ─────────────────────────────────────────────

class TestLogoutHandler:
    @pytest.mark.asyncio
    async def test_clears_credentials(self):
        from dcoder.commands.core.auth import LogoutHandler
        import os
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        ctx = _make_ctx(raw="/logout")
        res = await LogoutHandler().execute(ctx)
        assert res.success
        assert res.message is not None and "anthropic" in res.message.lower()
        assert "ANTHROPIC_API_KEY" not in os.environ

    @pytest.mark.asyncio
    async def test_logout_no_creds(self, monkeypatch):
        from dcoder.commands.core.auth import LogoutHandler
        with patch("dcoder.model.config.revoke_provider_credentials", return_value=[]):
            ctx = _make_ctx(raw="/logout")
            res = await LogoutHandler().execute(ctx)
            assert res.success
            assert res.message is not None and "No active credentials" in res.message


# ── /permissions ────────────────────────────────────────

class TestPermissionsHandler:
    @pytest.mark.asyncio
    async def test_show_scopes(self):
        from dcoder.commands.core.permissions import PermissionsHandler
        from dcoder.ui.permission_store import PermissionStore
        mock_app = MagicMock()
        mock_app._permission_store = PermissionStore()
        # bare /permissions with app → pushes modal (mount_as_app_message=False)
        ctx = _make_ctx(raw="/permissions", app=mock_app)
        res = await PermissionsHandler().execute(ctx)
        assert res.success
        # Modal pushed means no text message
        assert res.mount_as_app_message is False

    @pytest.mark.asyncio
    async def test_grant_valid_scope(self):
        from dcoder.commands.core.permissions import PermissionsHandler
        from dcoder.ui.permission_store import PermissionStore
        mock_app = MagicMock()
        store = PermissionStore()
        mock_app._permission_store = store
        ctx = _make_ctx(args="grant shell:write", raw="/permissions grant shell:write", app=mock_app)
        res = await PermissionsHandler().execute(ctx)
        assert res.success
        assert store.evaluate("shell:write") == "allow"

    @pytest.mark.asyncio
    async def test_revoke_valid_scope(self):
        from dcoder.commands.core.permissions import PermissionsHandler
        from dcoder.ui.permission_store import PermissionStore
        mock_app = MagicMock()
        store = PermissionStore()
        mock_app._permission_store = store
        ctx = _make_ctx(args="revoke shell:read", raw="/permissions revoke shell:read", app=mock_app)
        res = await PermissionsHandler().execute(ctx)
        assert res.success
        assert store.evaluate("shell:read") == "ask"

    @pytest.mark.asyncio
    async def test_permissions_reset(self):
        from dcoder.commands.core.permissions import PermissionsHandler
        from dcoder.ui.permission_store import PermissionStore
        mock_app = MagicMock()
        store = PermissionStore()
        store.add_rule("allow", "shell:write", source="session")
        mock_app._permission_store = store
        ctx = _make_ctx(args="reset", raw="/permissions reset", app=mock_app)
        res = await PermissionsHandler().execute(ctx)
        assert res.success
        # After reset, shell:write should be back to default (ask)
        assert store.evaluate("shell:write") == "ask"

    @pytest.mark.asyncio
    async def test_grant_tool_pattern(self):
        from dcoder.commands.core.permissions import PermissionsHandler
        from dcoder.ui.permission_store import PermissionStore
        mock_app = MagicMock()
        store = PermissionStore()
        mock_app._permission_store = store
        ctx = _make_ctx(args="grant Shell(kubectl get *)", raw="/permissions grant Shell(kubectl get *)", app=mock_app)
        res = await PermissionsHandler().execute(ctx)
        assert res.success
        assert res.message is not None and "Shell(kubectl get *)" in res.message

    @pytest.mark.asyncio
    async def test_set_mode(self):
        from dcoder.commands.core.permissions import PermissionsHandler
        from dcoder.ui.permission_store import PermissionStore
        mock_app = MagicMock()
        store = PermissionStore()
        mock_app._permission_store = store
        ctx = _make_ctx(args="mode strict", raw="/permissions mode strict", app=mock_app)
        res = await PermissionsHandler().execute(ctx)
        assert res.success
        assert store.mode == "strict"
        # In strict mode, everything requires approval
        assert store.evaluate("shell:read") == "ask"


# ── /mcp ────────────────────────────────────────────────

class TestMcpHandler:
    @pytest.mark.asyncio
    async def test_status_shows_servers(self):
        from dcoder.commands.core.mcp import McpHandler
        from dcoder.mcp.mcp_info import MCPServerInfo, MCPToolInfo
        mock_app = MagicMock()
        mock_app.get_mcp_servers.return_value = [
            MCPServerInfo(
                name="test-server",
                transport="stdio",
                tools=tuple(MCPToolInfo(name=f"tool_{i}") for i in range(5)),
                status="ok",
            )
        ]
        ctx = _make_ctx(args="status", raw="/mcp status", app=mock_app)
        res = await McpHandler().execute(ctx)
        assert res.success
        assert res.message is not None and "test-server" in res.message
        assert res.message is not None and "5 tools" in res.message

    @pytest.mark.asyncio
    async def test_no_args_opens_viewer(self):
        from dcoder.commands.core.mcp import McpHandler
        mock_app = MagicMock()
        mock_app.get_mcp_servers.return_value = []
        ctx = _make_ctx(args="", raw="/mcp", app=mock_app)
        res = await McpHandler().execute(ctx)
        assert res.success
        mock_app.push_screen.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_reconnect(self):
        from dcoder.commands.core.mcp import McpHandler
        mock_app = MagicMock()
        mock_app.reconnect_mcp_servers = AsyncMock(return_value=2)
        ctx = _make_ctx(args="reconnect", raw="/mcp reconnect", app=mock_app)
        res = await McpHandler().execute(ctx)
        assert res.success
        assert res.message is not None and "2 MCP server(s)" in res.message

    @pytest.mark.asyncio
    async def test_mcp_login(self):
        from dcoder.commands.core.mcp import McpHandler
        mock_app = MagicMock()
        ctx = _make_ctx(args="login github", raw="/mcp login github", app=mock_app)
        res = await McpHandler().execute(ctx)
        assert res.success
        mock_app._start_mcp_login.assert_called_once_with("github")



# ── /plugins ────────────────────────────────────────────

class TestPluginsHandler:
    @pytest.mark.asyncio
    async def test_no_plugins_available(self):
        from dcoder.commands.core.plugins import PluginsHandler
        mock_app = MagicMock(spec=[])  # No attributes
        ctx = _make_ctx(raw="/plugins", app=mock_app)
        res = await PluginsHandler().execute(ctx)
        assert res.success

    @pytest.mark.asyncio
    async def test_plugins_list_discovered(self):
        from dcoder.commands.core.plugins import PluginsHandler
        mock_plugin = MagicMock()
        mock_plugin.name = "k8s-plugin"
        mock_plugin.description = "Kubernetes tools"
        mock_plugin.healthy = True
        mock_app = MagicMock()
        mock_app._discovered_plugins = [mock_plugin]
        # Ensure _show_plugin_manager is not present
        del mock_app._show_plugin_manager
        ctx = _make_ctx(raw="/plugins", app=mock_app)
        res = await PluginsHandler().execute(ctx)
        assert res.success
        assert res.message is not None and "k8s-plugin" in res.message


# ── /skills ─────────────────────────────────────────────

class TestSkillsHandler:
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_empty_state(self):
        from dcoder.commands.core.skills import SkillsHandler
        mock_app = MagicMock(spec=[])  # No tool methods
        ctx = _make_ctx(raw="/skills", app=mock_app)
        res = await SkillsHandler().execute(ctx)
        assert res.success
        assert res.message is not None and "No skills found" in res.message

    @pytest.mark.asyncio
    async def test_skills_with_mcp_and_builtin(self):
        from dcoder.commands.core.skills import SkillsHandler
        from dcoder.mcp.mcp_info import MCPServerInfo, MCPToolInfo
        mock_app = MagicMock(spec=["get_active_tools", "get_mcp_servers", "get_discovered_skills"])
        mock_app.get_active_tools.return_value = [{"name": "run_command", "description": "Execute shell"}]
        mock_app.get_mcp_servers.return_value = [
            MCPServerInfo(
                name="alphavantage",
                transport="stdio",
                tools=(MCPToolInfo(name="GLOBAL_QUOTE", description="Stock quote"),),
                status="ok",
            )
        ]
        mock_app.get_discovered_skills.return_value = [{"name": "a11y-debugging", "description": "A11y tests"}]

        # /skills lists skills
        ctx_skills = _make_ctx(raw="/skills", app=mock_app)
        res_skills = await SkillsHandler().execute(ctx_skills)
        assert res_skills.success
        assert res_skills.message is not None and "a11y-debugging" in res_skills.message

        # /tools lists tools and MCP tools
        ctx_tools = _make_ctx(raw="/tools", app=mock_app)
        res_tools = await SkillsHandler().execute(ctx_tools)
        assert res_tools.success
        assert res_tools.message is not None and "run_command" in res_tools.message
        assert res_tools.message is not None and "GLOBAL_QUOTE" in res_tools.message


