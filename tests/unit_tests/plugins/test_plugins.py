"""Unit tests for DCoder scoped plugin installation enhancement.

Tests cover:
- Scoped enablement (user / project / local settings files)
- Scoped install registry (array-per-plugin in installed_plugins.json)
- Scope-aware uninstall (remove single scope, cache only when orphaned)
- Merged enablement across scopes
- CLI --scope flag parsing
- TUI _install_details_options with/without project
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dcoder.commands._base import CommandContext
from dcoder.plugins.manifest import build_inventory, load_manifest
from dcoder.plugins.marketplace import parse_marketplace_source
from dcoder.plugins.models import (
    InstallScope,
    InstalledPluginEntry,
    LocalMarketplaceSource,
    RepositoryMarketplaceSource,
    UrlMarketplaceSource,
    split_plugin_id,
)
from dcoder.plugins.store import (
    _load_settings_enabled_plugins,
    _write_settings_enabled_plugins,
    add_installed_plugin,
    load_all_enabled_plugin_ids,
    load_enabled_plugin_ids,
    load_installed_plugin_entries,
    load_installed_plugins,
    load_local_enabled_plugin_ids,
    load_project_enabled_plugin_ids,
    load_user_enabled_plugin_ids,
    remove_installed_plugin,
    set_plugin_enabled,
    set_plugin_enabled_for_scope,
    uninstall_plugin,
)


# ── Existing tests (preserved) ──────────────────────────────


def test_split_plugin_id():
    name, mp = split_plugin_id("terraform@built-in")
    assert name == "terraform"
    assert mp == "built-in"

    with pytest.raises(ValueError):
        split_plugin_id("invalid-id")


def test_parse_marketplace_source():
    src_gh = parse_marketplace_source("owner/repo")
    assert isinstance(src_gh, RepositoryMarketplaceSource)
    assert src_gh.value == "owner/repo"

    src_url = parse_marketplace_source("https://example.com/marketplace.json")
    assert isinstance(src_url, UrlMarketplaceSource)

    src_dir = parse_marketplace_source("./")
    assert isinstance(src_dir, LocalMarketplaceSource)


def test_load_manifest_and_inventory(tmp_path):
    plugin_dir = tmp_path / "my_plugin"
    plugin_dir.mkdir()
    manifest_file = plugin_dir / "plugin.json"
    manifest_file.write_text(
        json.dumps(
            {
                "name": "test-plugin",
                "version": "1.2.3",
                "displayName": "Test Plugin",
                "skills": "./skills",
            }
        ),
        encoding="utf-8",
    )
    skills_dir = plugin_dir / "skills"
    skills_dir.mkdir()
    (skills_dir / "SKILL.md").write_text("# Skill", encoding="utf-8")

    manifest, path, warnings = load_manifest(plugin_dir)
    assert manifest is not None
    assert manifest.name == "test-plugin"
    assert manifest.version == "1.2.3"
    assert manifest.display_name == "Test Plugin"

    inventory = build_inventory(plugin_dir, manifest, warnings)
    assert len(inventory.skills) == 1


# ── Scoped Enablement Tests ──────────────────────────────────


class TestScopedEnablement:
    """Tests for scoped settings.json enablement files."""

    def test_write_and_read_settings_enabled_plugins(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        _write_settings_enabled_plugins(settings_file, {"a@mp", "b@mp"})

        result = _load_settings_enabled_plugins(settings_file)
        assert result == frozenset({"a@mp", "b@mp"})

    def test_read_nonexistent_settings_file(self, tmp_path):
        result = _load_settings_enabled_plugins(tmp_path / "missing.json")
        assert result == frozenset()

    def test_read_corrupt_settings_file(self, tmp_path):
        bad_file = tmp_path / "settings.json"
        bad_file.write_text("not-json!!!", encoding="utf-8")
        result = _load_settings_enabled_plugins(bad_file)
        assert result == frozenset()

    def test_preserves_other_keys(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(
            json.dumps({"customKey": "value", "enabledPlugins": {"old@mp": True}}),
            encoding="utf-8",
        )
        _write_settings_enabled_plugins(settings_file, {"new@mp"})
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        assert data["customKey"] == "value"
        assert data["enabledPlugins"] == {"new@mp": True}

    def test_user_scope_enablement(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dcoder.plugins.store._user_settings_path", lambda: tmp_path / "settings.json"
        )
        set_plugin_enabled("test@mp", True)
        assert "test@mp" in load_user_enabled_plugin_ids()

        set_plugin_enabled("test@mp", False)
        assert "test@mp" not in load_user_enabled_plugin_ids()

    def test_project_scope_enablement(self, tmp_path, monkeypatch):
        from dcoder.config import paths
        project_root = tmp_path / "myproject"
        project_root.mkdir()
        (project_root / ".dcoder").mkdir()

        monkeypatch.setattr(
            paths, "project_settings_path",
            lambda pr: pr / ".dcoder" / "settings.json",
        )
        set_plugin_enabled_for_scope("test@mp", True, scope="project", project_root=project_root)
        result = load_project_enabled_plugin_ids(project_root)
        assert "test@mp" in result

    def test_local_scope_enablement(self, tmp_path, monkeypatch):
        from dcoder.config import paths
        project_root = tmp_path / "myproject"
        project_root.mkdir()
        (project_root / ".dcoder").mkdir()

        monkeypatch.setattr(
            paths, "project_local_settings_path",
            lambda pr: pr / ".dcoder" / "settings.local.json",
        )
        # Patch out _ensure_local_settings_gitignored so it doesn't touch real git config
        monkeypatch.setattr(
            "dcoder.plugins.store._ensure_local_settings_gitignored", lambda _: None,
        )
        set_plugin_enabled_for_scope("test@mp", True, scope="local", project_root=project_root)
        result = load_local_enabled_plugin_ids(project_root)
        assert "test@mp" in result

    def test_merged_enablement(self, tmp_path, monkeypatch):
        from dcoder.config import paths

        user_settings = tmp_path / "user" / "settings.json"
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".dcoder").mkdir()

        monkeypatch.setattr(
            "dcoder.plugins.store._user_settings_path", lambda: user_settings
        )
        monkeypatch.setattr(
            paths, "project_settings_path",
            lambda pr: pr / ".dcoder" / "settings.json",
        )
        monkeypatch.setattr(
            paths, "project_local_settings_path",
            lambda pr: pr / ".dcoder" / "settings.local.json",
        )

        _write_settings_enabled_plugins(user_settings, {"user-plugin@mp"})
        _write_settings_enabled_plugins(
            project_root / ".dcoder" / "settings.json", {"project-plugin@mp"}
        )
        _write_settings_enabled_plugins(
            project_root / ".dcoder" / "settings.local.json", {"local-plugin@mp"}
        )

        merged = load_all_enabled_plugin_ids(project_root=project_root)
        assert merged == frozenset({"user-plugin@mp", "project-plugin@mp", "local-plugin@mp"})

    def test_merged_without_project(self, tmp_path, monkeypatch):
        user_settings = tmp_path / "settings.json"
        monkeypatch.setattr(
            "dcoder.plugins.store._user_settings_path", lambda: user_settings
        )
        _write_settings_enabled_plugins(user_settings, {"user-only@mp"})

        merged = load_all_enabled_plugin_ids(project_root=None)
        assert merged == frozenset({"user-only@mp"})

    def test_scope_validation(self):
        with pytest.raises(ValueError, match="project_root required"):
            set_plugin_enabled_for_scope("x@mp", True, scope="project")
        with pytest.raises(ValueError, match="project_root required"):
            set_plugin_enabled_for_scope("x@mp", True, scope="local")

    def test_backward_compat_load_enabled(self, tmp_path, monkeypatch):
        """load_enabled_plugin_ids() reads from user settings."""
        user_settings = tmp_path / "settings.json"
        monkeypatch.setattr(
            "dcoder.plugins.store._user_settings_path", lambda: user_settings
        )
        _write_settings_enabled_plugins(user_settings, {"compat@mp"})
        result = load_enabled_plugin_ids()
        assert "compat@mp" in result


# ── Scoped Install Registry Tests ────────────────────────────


class TestScopedInstallRegistry:
    """Tests for array-per-plugin install registry with scope metadata."""

    def test_add_scoped_install_entry(self, tmp_path, monkeypatch):
        state_dir = tmp_path / "state"
        monkeypatch.setattr("dcoder.plugins.store._installed_plugins_path", lambda: state_dir / "installed_plugins.json")

        entry = add_installed_plugin(
            "test@mp",
            install_path=str(tmp_path / "cache" / "test"),
            version="1.0.0",
            scope="user",
        )
        assert entry.scope == "user"
        assert entry.installed_at is not None

        all_entries = load_installed_plugin_entries()
        assert "test@mp" in all_entries
        assert len(all_entries["test@mp"]) == 1
        assert all_entries["test@mp"][0].scope == "user"

    def test_multi_scope_install(self, tmp_path, monkeypatch):
        """Same plugin installed at user and project scope simultaneously."""
        state_dir = tmp_path / "state"
        monkeypatch.setattr("dcoder.plugins.store._installed_plugins_path", lambda: state_dir / "installed_plugins.json")

        project_root = tmp_path / "myproject"
        project_root.mkdir()

        add_installed_plugin(
            "test@mp",
            install_path=str(tmp_path / "cache" / "test"),
            version="1.0.0",
            scope="user",
        )
        add_installed_plugin(
            "test@mp",
            install_path=str(tmp_path / "cache" / "test"),
            version="1.0.0",
            scope="project",
            project_root=project_root,
        )

        all_entries = load_installed_plugin_entries()
        assert len(all_entries["test@mp"]) == 2
        scopes = {e.scope for e in all_entries["test@mp"]}
        assert scopes == {"user", "project"}

    def test_replace_same_scope_entry(self, tmp_path, monkeypatch):
        """Re-installing at the same scope replaces the existing entry."""
        state_dir = tmp_path / "replace_test_state"
        monkeypatch.setattr("dcoder.plugins.store._installed_plugins_path", lambda: state_dir / "installed_plugins.json")

        add_installed_plugin(
            "test@mp",
            install_path=str(tmp_path / "cache" / "v1"),
            version="1.0.0",
            scope="user",
        )
        add_installed_plugin(
            "test@mp",
            install_path=str(tmp_path / "cache" / "v2"),
            version="2.0.0",
            scope="user",
        )

        all_entries = load_installed_plugin_entries()
        assert len(all_entries["test@mp"]) == 1
        assert all_entries["test@mp"][0].version == "2.0.0"

    def test_backward_compat_load_installed(self, tmp_path, monkeypatch):
        """load_installed_plugins() returns first entry per plugin."""
        state_dir = tmp_path / "compat_test_state"
        monkeypatch.setattr("dcoder.plugins.store._installed_plugins_path", lambda: state_dir / "installed_plugins.json")

        project_root = tmp_path / "proj"
        project_root.mkdir()

        add_installed_plugin(
            "test@mp",
            install_path="/cache/user",
            version="1.0.0",
            scope="user",
        )
        add_installed_plugin(
            "test@mp",
            install_path="/cache/user",
            version="1.0.0",
            scope="project",
            project_root=project_root,
        )

        installed = load_installed_plugins()
        assert "test@mp" in installed
        # Returns single entry (first one = user)
        assert installed["test@mp"].scope == "user"

    def test_json_serialization_roundtrip(self, tmp_path, monkeypatch):
        """Verify all new fields survive a JSON roundtrip."""
        state_dir = tmp_path / "roundtrip_test_state"
        monkeypatch.setattr("dcoder.plugins.store._installed_plugins_path", lambda: state_dir / "installed_plugins.json")

        project_root = tmp_path / "proj"
        project_root.mkdir()

        add_installed_plugin(
            "test@mp",
            install_path="/cache/test",
            version="3.0.0",
            scope="local",
            project_root=project_root,
            git_commit_sha="abc123",
        )

        all_entries = load_installed_plugin_entries()
        entry = all_entries["test@mp"][0]
        assert entry.scope == "local"
        assert entry.project_path == str(project_root)
        assert entry.git_commit_sha == "abc123"
        assert entry.installed_at is not None


# ── Scope-Aware Uninstall Tests ──────────────────────────────


class TestScopedUninstall:
    """Tests for scope-aware uninstall logic."""

    def test_remove_single_scope(self, tmp_path, monkeypatch):
        state_dir = tmp_path / "remove_single_state"
        monkeypatch.setattr("dcoder.plugins.store._installed_plugins_path", lambda: state_dir / "installed_plugins.json")

        project_root = tmp_path / "proj"
        project_root.mkdir()

        add_installed_plugin(
            "test@mp", install_path="/cache/test", version="1.0.0", scope="user"
        )
        add_installed_plugin(
            "test@mp",
            install_path="/cache/test",
            version="1.0.0",
            scope="project",
            project_root=project_root,
        )

        removed = remove_installed_plugin(
            "test@mp", scope="project", project_root=project_root
        )
        assert removed is not None
        assert removed.scope == "project"

        remaining = load_installed_plugin_entries()
        assert len(remaining["test@mp"]) == 1
        assert remaining["test@mp"][0].scope == "user"

    def test_remove_all_scopes(self, tmp_path, monkeypatch):
        state_dir = tmp_path / "remove_all_state"
        monkeypatch.setattr("dcoder.plugins.store._installed_plugins_path", lambda: state_dir / "installed_plugins.json")

        add_installed_plugin(
            "test@mp", install_path="/cache/test", version="1.0.0", scope="user"
        )

        removed = remove_installed_plugin("test@mp")  # scope=None => remove all
        assert removed is not None

        remaining = load_installed_plugin_entries()
        assert "test@mp" not in remaining

    def test_uninstall_deletes_cache_only_when_orphaned(self, tmp_path, monkeypatch):
        state_dir = tmp_path / "uninstall_orphan_state"
        monkeypatch.setattr("dcoder.plugins.store._installed_plugins_path", lambda: state_dir / "installed_plugins.json")
        monkeypatch.setattr(
            "dcoder.plugins.store._user_settings_path",
            lambda: tmp_path / "settings.json",
        )

        cache_dir = tmp_path / "cache" / "test"
        cache_dir.mkdir(parents=True)
        (cache_dir / "plugin.json").write_text("{}", encoding="utf-8")

        project_root = tmp_path / "proj"
        project_root.mkdir()

        add_installed_plugin(
            "test@mp", install_path=str(cache_dir), version="1.0.0", scope="user"
        )
        add_installed_plugin(
            "test@mp",
            install_path=str(cache_dir),
            version="1.0.0",
            scope="project",
            project_root=project_root,
        )

        # Uninstall project scope only — cache should survive
        from dcoder.config import paths
        monkeypatch.setattr(
            paths, "project_settings_path",
            lambda pr: pr / ".dcoder" / "settings.json",
        )
        (project_root / ".dcoder").mkdir(exist_ok=True)

        uninstall_plugin("test@mp", scope="project", project_root=project_root)
        assert cache_dir.is_dir(), "Cache should survive when user scope still references it"

        # Now uninstall user scope — cache should be deleted
        uninstall_plugin("test@mp", scope="user")
        assert not cache_dir.is_dir(), "Cache should be deleted when no scopes reference it"


# ── TUI Options Tests ────────────────────────────────────────


class TestTUIInstallOptions:
    """Tests for _install_details_options."""

    def test_options_without_project(self):
        from dcoder.ui.widgets.plugin_manager import _install_details_options

        options = _install_details_options(has_project=False)
        ids = [o.id for o in options]
        assert "action:install-user" in ids
        assert "action:install-project" not in ids
        assert "action:install-local" not in ids
        assert "details-back" in ids

    def test_options_with_project(self):
        from dcoder.ui.widgets.plugin_manager import _install_details_options

        options = _install_details_options(has_project=True)
        ids = [o.id for o in options]
        assert "action:install-user" in ids
        assert "action:install-project" in ids
        assert "action:install-local" in ids
        assert "details-back" in ids


# ── CLI --scope Tests ────────────────────────────────────────


class TestCLIScopeFlag:
    """Tests for CLI --scope argument parsing."""

    def test_install_parser_has_scope(self):
        import argparse
        from dcoder.plugins.commands_cli import setup_plugin_parser

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        setup_plugin_parser(sub)

        args = parser.parse_args(["plugin", "install", "test@mp", "--scope", "project"])
        assert args.plugin_id == "test@mp"
        assert args.scope == "project"

    def test_install_parser_default_scope(self):
        import argparse
        from dcoder.plugins.commands_cli import setup_plugin_parser

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        setup_plugin_parser(sub)

        args = parser.parse_args(["plugin", "install", "test@mp"])
        assert args.scope == "user"

    def test_uninstall_parser_scope_optional(self):
        import argparse
        from dcoder.plugins.commands_cli import setup_plugin_parser

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        setup_plugin_parser(sub)

        args = parser.parse_args(["plugin", "uninstall", "test@mp"])
        assert args.scope is None

        args_scoped = parser.parse_args(
            ["plugin", "uninstall", "test@mp", "--scope", "local"]
        )
        assert args_scoped.scope == "local"

    def test_enable_disable_scope(self):
        import argparse
        from dcoder.plugins.commands_cli import setup_plugin_parser

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        setup_plugin_parser(sub)

        args = parser.parse_args(
            ["plugin", "enable", "test@mp", "--scope", "project"]
        )
        assert args.scope == "project"


# ── InstalledPluginEntry Model Tests ─────────────────────────


class TestInstalledPluginEntryModel:
    """Tests for InstalledPluginEntry dataclass with scope fields."""

    def test_default_scope_is_user(self):
        entry = InstalledPluginEntry(install_path="/test", version="1.0.0")
        assert entry.scope == "user"
        assert entry.project_path is None
        assert entry.installed_at is None
        assert entry.git_commit_sha is None

    def test_full_construction(self):
        entry = InstalledPluginEntry(
            install_path="/test",
            version="1.0.0",
            scope="project",
            project_path="/my/project",
            installed_at="2024-01-01T00:00:00Z",
            last_updated="2024-01-01T00:00:00Z",
            git_commit_sha="abc123",
        )
        assert entry.scope == "project"
        assert entry.project_path == "/my/project"
        assert entry.git_commit_sha == "abc123"


# ── Backward-compat full store test (updated) ────────────────


def test_plugin_store_operations(tmp_path, monkeypatch):
    storage_dir = tmp_path / "dcoder_test"
    monkeypatch.setenv("DCODER_PLUGIN_DIR", str(storage_dir))
    monkeypatch.setattr("dcoder.plugins.store._installed_plugins_path", lambda: storage_dir / "installed_plugins.json")
    monkeypatch.setattr(
        "dcoder.plugins.store._user_settings_path",
        lambda: tmp_path / "settings.json",
    )

    add_installed_plugin("test@official", install_path=str(tmp_path), version="1.0.0")
    installed = load_installed_plugins()
    assert "test@official" in installed
    assert installed["test@official"].version == "1.0.0"
    assert installed["test@official"].scope == "user"

    set_plugin_enabled("test@official", True)
    enabled = load_enabled_plugin_ids()
    assert "test@official" in enabled

    set_plugin_enabled("test@official", False)
    enabled = load_enabled_plugin_ids()
    assert "test@official" not in enabled

    remove_installed_plugin("test@official")
    installed = load_installed_plugins()
    assert "test@official" not in installed


@pytest.mark.asyncio
async def test_plugins_handler_tui_push():
    from dcoder.commands.core.plugins import PluginsHandler

    mock_app = MagicMock()
    ctx = CommandContext(
        app=mock_app,
        settings=MagicMock(),
        raw_command="/plugins",
        args="",
    )
    res = await PluginsHandler().execute(ctx)
    assert res.success
    mock_app._show_plugin_manager.assert_called_once()


@pytest.mark.asyncio
async def test_plugins_handler_cli_fallback():
    from dcoder.commands.core.plugins import PluginsHandler

    ctx = CommandContext(
        app=None,
        settings=MagicMock(),
        raw_command="/plugins",
        args="",
    )
    res = await PluginsHandler().execute(ctx)
    assert res.success
    assert res.message is not None
    assert "Plugins" in res.message or "No plugins" in res.message


# ── Component Inventory Detection Tests ──────────────────────────


class TestBuildInventoryDetection:
    """Tests for build_inventory detecting all component types."""

    def test_build_inventory_detects_agents_dir(self, tmp_path):
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        agents_dir = plugin_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "reviewer.md").write_text(
            "---\nname: reviewer\ndescription: Review\n---\nPrompt",
            encoding="utf-8",
        )

        inventory = build_inventory(plugin_dir, None)
        assert len(inventory.agents) == 1
        assert inventory.agents[0].name == "agents"

    def test_build_inventory_detects_mcp_json(self, tmp_path):
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        (plugin_dir / ".mcp.json").write_text(
            '{"mcpServers": {"test": {"command": "echo"}}}',
            encoding="utf-8",
        )

        inventory = build_inventory(plugin_dir, None)
        assert len(inventory.mcp_files) == 1
        assert inventory.mcp_files[0].name == ".mcp.json"

    def test_build_inventory_with_all_components(self, tmp_path):
        """Plugin with skills + agents + commands + mcp all detected."""
        plugin_dir = tmp_path / "full_plugin"
        plugin_dir.mkdir()

        # Skills
        skills_dir = plugin_dir / "skills"
        skill_sub = skills_dir / "my-skill"
        skill_sub.mkdir(parents=True)
        (skill_sub / "SKILL.md").write_text("# Skill", encoding="utf-8")

        # Agents
        agents_dir = plugin_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "my-agent.md").write_text(
            "---\nname: ag\ndescription: Agent\n---\nPrompt", encoding="utf-8",
        )

        # Commands
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir()
        (commands_dir / "run.md").write_text("# Run cmd", encoding="utf-8")

        # MCP
        (plugin_dir / ".mcp.json").write_text(
            '{"mcpServers": {"srv": {"command": "x"}}}', encoding="utf-8",
        )

        inventory = build_inventory(plugin_dir, None)
        assert len(inventory.skills) >= 1
        assert len(inventory.agents) >= 1
        assert len(inventory.commands) >= 1
        assert len(inventory.mcp_files) >= 1

    def test_build_inventory_empty_plugin(self, tmp_path):
        """Empty plugin root → empty inventory, no crash."""
        plugin_dir = tmp_path / "empty"
        plugin_dir.mkdir()

        inventory = build_inventory(plugin_dir, None)
        assert inventory.skills == ()
        assert inventory.agents == ()
        assert inventory.commands == ()
        assert inventory.mcp_files == ()

    def test_build_inventory_with_manifest_paths(self, tmp_path):
        """Manifest-declared component paths are resolved."""
        plugin_dir = tmp_path / "manifest_plugin"
        plugin_dir.mkdir()

        custom_skills = plugin_dir / "custom_skills"
        custom_skills.mkdir()

        manifest_file = plugin_dir / "plugin.json"
        manifest_file.write_text(
            json.dumps({
                "name": "manifest-plugin",
                "skills": "./custom_skills",
            }),
            encoding="utf-8",
        )

        manifest, _, warnings = load_manifest(plugin_dir)
        inventory = build_inventory(plugin_dir, manifest, warnings)
        assert len(inventory.skills) >= 1
        # Should resolve to custom_skills dir
        assert any("custom_skills" in str(p) for p in inventory.skills)
