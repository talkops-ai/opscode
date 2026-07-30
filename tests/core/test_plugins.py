"""Unit tests for DCoder plugin enhancement, store, discovery, and TUI widgets."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dcoder.commands._base import CommandContext
from dcoder.plugins.manifest import build_inventory, load_manifest
from dcoder.plugins.marketplace import parse_marketplace_source
from dcoder.plugins.models import (
    LocalMarketplaceSource,
    RepositoryMarketplaceSource,
    UrlMarketplaceSource,
    split_plugin_id,
)
from dcoder.plugins.store import (
    add_installed_plugin,
    load_enabled_plugin_ids,
    load_installed_plugins,
    remove_installed_plugin,
    set_plugin_enabled,
)


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


def test_plugin_store_operations(tmp_path, monkeypatch):
    storage_dir = tmp_path / "dcoder_test"
    monkeypatch.setenv("DCODER_PLUGIN_DIR", str(storage_dir))
    monkeypatch.setattr("dcoder.plugins.store._state_dir", lambda: storage_dir)

    add_installed_plugin("test@official", install_path=str(tmp_path), version="1.0.0")
    installed = load_installed_plugins()
    assert "test@official" in installed
    assert installed["test@official"].version == "1.0.0"

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

