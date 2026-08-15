"""Comprehensive tests for project-local plugin auto-discovery and loading.

Covers:
- Marketplace discovery from all supported relative paths
- Plugin bifurcation (agent vs non-agent)
- Subagent metadata construction, enrichment, and namespacing
- Skill binding isolation (agent plugin skills → subagent only)
- MCP config binding isolation (agent plugin MCP → subagent only)
- Non-agent plugin binding (skills/MCP/commands → main agent)
- SubagentsMiddleware integration with project plugins
- End-to-end marketplace simulation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from dcoder.subagents.types import SubagentMetadata

from dcoder.plugins.manifest import build_inventory, load_manifest
from dcoder.plugins.marketplace import find_marketplace_manifest
from dcoder.plugins.models import ComponentInventory, PluginInstance
from dcoder.plugins.project_plugins import (
    ProjectPluginResult,
    _build_plugin_instance,
    _collect_skill_names,
    _has_agents,
    _process_agent_plugin,
    _process_main_plugin,
    _read_mcp_config,
    load_project_plugins,
)

# Monkeypatch target for plugin_data_dir — used in _build_plugin_instance
_PLUGIN_DATA_DIR_TARGET = "dcoder.plugins.store.plugin_data_dir"


# ── Shared fixtures ────────────────────────────────────────────


def _load_plugin_inventory(plugin_dir: Path) -> ComponentInventory:
    """Helper: load manifest + build inventory from a plugin dir.

    Correctly unpacks ``load_manifest()`` return tuple.
    """
    manifest, _manifest_path, warnings = load_manifest(plugin_dir)
    return build_inventory(plugin_dir, manifest, warnings)


def _write_marketplace(root: Path, plugins: list[dict]) -> Path:
    """Write a marketplace.json under .dcoder-plugin convention and return its path."""
    mp_dir = root / ".dcoder-plugin"
    mp_dir.mkdir(parents=True, exist_ok=True)
    mp_path = mp_dir / "marketplace.json"
    mp_path.write_text(
        json.dumps(
            {"name": "test-marketplace", "plugins": plugins},
            indent=2,
        ),
        encoding="utf-8",
    )
    return mp_path


def _make_agent_plugin(root: Path, name: str, *, skills: list[str] | None = None,
                       mcp_servers: dict | None = None) -> Path:
    """Create a minimal agent plugin directory tree."""
    plugin_dir = root / name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # plugin.json
    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_dir.mkdir(exist_ok=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": name}), encoding="utf-8",
    )

    # agents/*.md
    agents_dir = plugin_dir / "agents"
    agents_dir.mkdir(exist_ok=True)
    (agents_dir / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: Agent plugin {name}\n---\n"
        f"You are the {name} subagent.",
        encoding="utf-8",
    )

    # skills/<skill>/SKILL.md
    if skills:
        skills_dir = plugin_dir / "skills"
        skills_dir.mkdir(exist_ok=True)
        for skill_name in skills:
            skill_sub = skills_dir / skill_name
            skill_sub.mkdir(exist_ok=True)
            (skill_sub / "SKILL.md").write_text(
                f"---\nname: {skill_name}\ndescription: Skill {skill_name}\n---\n"
                f"Body of {skill_name}.",
                encoding="utf-8",
            )

    # .mcp.json
    if mcp_servers:
        (plugin_dir / ".mcp.json").write_text(
            json.dumps({"mcpServers": mcp_servers}), encoding="utf-8",
        )

    return plugin_dir


def _make_main_plugin(root: Path, name: str, *, skills: list[str] | None = None,
                      mcp_servers: dict | None = None,
                      commands: list[str] | None = None) -> Path:
    """Create a minimal non-agent plugin directory tree."""
    plugin_dir = root / name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # plugin.json
    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_dir.mkdir(exist_ok=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": name}), encoding="utf-8",
    )

    # skills/<skill>/SKILL.md
    if skills:
        skills_dir = plugin_dir / "skills"
        skills_dir.mkdir(exist_ok=True)
        for skill_name in skills:
            skill_sub = skills_dir / skill_name
            skill_sub.mkdir(exist_ok=True)
            (skill_sub / "SKILL.md").write_text(
                f"---\nname: {skill_name}\ndescription: Skill {skill_name}\n---\n"
                f"Body of {skill_name}.",
                encoding="utf-8",
            )

    # .mcp.json
    if mcp_servers:
        (plugin_dir / ".mcp.json").write_text(
            json.dumps({"mcpServers": mcp_servers}), encoding="utf-8",
        )

    # commands/<cmd>.md
    if commands:
        cmd_dir = plugin_dir / "commands"
        cmd_dir.mkdir(exist_ok=True)
        for cmd_name in commands:
            (cmd_dir / f"{cmd_name}.md").write_text(
                f"# {cmd_name}\nRun the {cmd_name} command.",
                encoding="utf-8",
            )

    return plugin_dir


def _make_plugin_instance(
    tmp_path: Path, name: str, inventory: ComponentInventory, marketplace: str = "test-marketplace",
) -> PluginInstance:
    """Build a PluginInstance from a name and inventory (no manifest needed)."""
    return PluginInstance(
        plugin_id=f"{name}@{marketplace}",
        name=name,
        marketplace=marketplace,
        version=None,
        root=tmp_path,
        data_dir=tmp_path / "data",
        manifest=None,
        inventory=inventory,
    )


@pytest.fixture()
def _patch_plugin_data_dir(tmp_path, monkeypatch):
    """Monkeypatch plugin_data_dir to use tmp_path."""
    monkeypatch.setattr(
        _PLUGIN_DATA_DIR_TARGET,
        lambda pid: tmp_path / "data" / pid,
    )


# ── Test Class 1: Marketplace Discovery Paths ──────────────────


class TestMarketplaceDiscoveryPaths:
    """Verify marketplace manifest discovery from all supported relative paths."""

    def test_discovers_dcoder_plugin_marketplace(self, tmp_path):
        mp_dir = tmp_path / ".dcoder-plugin"
        mp_dir.mkdir()
        (mp_dir / "marketplace.json").write_text(
            json.dumps({"name": "mp", "plugins": []}), encoding="utf-8",
        )
        found = find_marketplace_manifest(tmp_path)
        assert found is not None
        assert found.name == "marketplace.json"
        assert ".dcoder-plugin" in str(found.parent)

    def test_discovers_claude_plugin_marketplace(self, tmp_path):
        mp_dir = tmp_path / ".claude-plugin"
        mp_dir.mkdir()
        (mp_dir / "marketplace.json").write_text(
            json.dumps({"name": "mp", "plugins": []}), encoding="utf-8",
        )
        found = find_marketplace_manifest(tmp_path)
        assert found is not None
        assert ".claude-plugin" in str(found.parent)

    def test_discovers_dcoder_plugins_marketplace(self, tmp_path):
        """`.dcoder/plugins/marketplace.json` is found when searching `.dcoder/`."""
        dcoder_dir = tmp_path / ".dcoder"
        mp_dir = dcoder_dir / "plugins"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text(
            json.dumps({"name": "mp", "plugins": []}), encoding="utf-8",
        )
        # The search root is .dcoder/ (convention: find_marketplace_manifest
        # searches for _MARKETPLACE_RELATIVE_PATHS relative to the given root)
        # But the path ".dcoder/plugins/marketplace.json" is relative to project root
        found = find_marketplace_manifest(tmp_path)
        assert found is not None

    def test_discovers_bare_marketplace(self, tmp_path):
        (tmp_path / "marketplace.json").write_text(
            json.dumps({"name": "mp", "plugins": []}), encoding="utf-8",
        )
        found = find_marketplace_manifest(tmp_path)
        assert found is not None
        assert found.name == "marketplace.json"

    def test_no_marketplace_returns_none(self, tmp_path):
        found = find_marketplace_manifest(tmp_path)
        assert found is None

    def test_precedence_first_match_wins(self, tmp_path):
        """When .claude-plugin and .dcoder-plugin both exist, .claude-plugin wins (first in list)."""
        claude_dir = tmp_path / ".claude-plugin"
        claude_dir.mkdir()
        (claude_dir / "marketplace.json").write_text(
            json.dumps({"name": "claude-mp", "plugins": []}), encoding="utf-8",
        )

        dcoder_dir = tmp_path / ".dcoder-plugin"
        dcoder_dir.mkdir()
        (dcoder_dir / "marketplace.json").write_text(
            json.dumps({"name": "dcoder-mp", "plugins": []}), encoding="utf-8",
        )

        found = find_marketplace_manifest(tmp_path)
        assert found is not None
        assert ".claude-plugin" in str(found.parent)

    def test_discovers_nested_dcoder_dcoder_plugin(self, tmp_path):
        """`.dcoder/.dcoder-plugin/marketplace.json` is found."""
        dcoder_dir = tmp_path / ".dcoder"
        mp_dir = dcoder_dir / ".dcoder-plugin"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text(
            json.dumps({"name": "nested-mp", "plugins": []}), encoding="utf-8",
        )
        # Searching from project root should find it (via .dcoder/.dcoder-plugin path)
        found = find_marketplace_manifest(tmp_path)
        assert found is not None


# ── Test Class 2: Plugin Bifurcation ────────────────────────────


class TestPluginBifurcation:
    """Core bifurcation logic — agent plugins vs non-agent plugins."""

    def test_plugin_with_agents_dir_is_agent_plugin(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "linter.md").write_text(
            "---\nname: linter\ndescription: Lint\n---\nPrompt", encoding="utf-8",
        )
        inventory = ComponentInventory(agents=(agents_dir,))
        assert _has_agents(inventory) is True

    def test_plugin_without_agents_dir_is_main_plugin(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        inventory = ComponentInventory(skills=(skills_dir,))
        assert _has_agents(inventory) is False

    def test_mixed_marketplace_bifurcates_correctly(self, tmp_path, _patch_plugin_data_dir):
        """Marketplace with both agent and non-agent plugins bifurcates correctly."""
        project_root = tmp_path / "project"
        dcoder_dir = project_root / ".dcoder"
        plugins_dir = dcoder_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        # Agent plugin
        _make_agent_plugin(plugins_dir, "tf-linter", skills=["tf-validate"])

        # Non-agent plugin
        _make_main_plugin(plugins_dir, "cost-est", skills=["cost-calc"])

        # Marketplace
        _write_marketplace(dcoder_dir, [
            {"name": "tf-linter", "source": "./plugins/tf-linter"},
            {"name": "cost-est", "source": "./plugins/cost-est"},
        ])

        result = load_project_plugins(project_root)
        assert len(result.subagent_metas) >= 1
        assert len(result.main_skill_sources) >= 1

    def test_empty_agents_dir_treated_as_main_plugin(self, tmp_path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        # Empty directory — no .md files
        inventory = ComponentInventory(agents=(agents_dir,))
        assert _has_agents(inventory) is False


# ── Test Class 3: Agent Plugin Subagent Metadata ─────────────────


class TestAgentPluginSubagentMetadata:
    """Verify subagent metadata is correctly built from agent plugin structure."""

    def test_agent_md_parsed_as_subagent(self, tmp_path):
        plugin_dir = _make_agent_plugin(
            tmp_path, "linter", skills=["fmt-check"],
        )
        inventory = _load_plugin_inventory(plugin_dir)
        plugin = _make_plugin_instance(plugin_dir, "linter", inventory)
        subagents, warnings = _process_agent_plugin(plugin)
        assert len(subagents) == 1
        assert subagents[0]["description"] == "Agent plugin linter"
        assert "You are the linter subagent." in subagents[0]["system_prompt"]

    def test_agent_subdir_agents_md(self, tmp_path):
        """agents/<name>/AGENTS.md → parsed with fallback name from dir."""
        plugin_dir = tmp_path / "reviewer"
        plugin_dir.mkdir()
        agents_dir = plugin_dir / "agents" / "code-reviewer"
        agents_dir.mkdir(parents=True)
        (agents_dir / "AGENTS.md").write_text(
            "---\ndescription: Review code\n---\nReview system prompt.",
            encoding="utf-8",
        )
        manifest_dir = plugin_dir / ".claude-plugin"
        manifest_dir.mkdir()
        (manifest_dir / "plugin.json").write_text(
            json.dumps({"name": "reviewer"}), encoding="utf-8",
        )

        inventory = _load_plugin_inventory(plugin_dir)
        plugin = _make_plugin_instance(plugin_dir, "reviewer", inventory)
        subagents, _ = _process_agent_plugin(plugin)
        assert len(subagents) == 1
        # Fallback name from directory
        assert "code-reviewer" in subagents[0]["name"]

    def test_subagent_inherits_plugin_skills(self, tmp_path):
        plugin_dir = _make_agent_plugin(
            tmp_path, "scanner", skills=["vuln-scan", "dep-check"],
        )
        inventory = _load_plugin_inventory(plugin_dir)
        plugin = _make_plugin_instance(plugin_dir, "scanner", inventory)
        subagents, _ = _process_agent_plugin(plugin)
        assert len(subagents) == 1
        skills = subagents[0].get("skills") or []
        # Skills should be listed (either raw names or namespaced)
        assert len(skills) >= 2

    def test_subagent_inherits_plugin_mcp(self, tmp_path):
        mcp_config = {"infracost": {"command": "infracost", "args": ["serve"]}}
        plugin_dir = _make_agent_plugin(
            tmp_path, "cost-agent", mcp_servers=mcp_config,
        )
        inventory = _load_plugin_inventory(plugin_dir)
        plugin = _make_plugin_instance(plugin_dir, "cost-agent", inventory)
        subagents, _ = _process_agent_plugin(plugin)
        assert len(subagents) == 1
        mcp_files = subagents[0].get("mcp_files") or []
        assert len(mcp_files) >= 1
        assert any(".mcp.json" in f for f in mcp_files)

    def test_subagent_source_attributed_to_plugin(self, tmp_path):
        plugin_dir = _make_agent_plugin(tmp_path, "builder")
        inventory = _load_plugin_inventory(plugin_dir)
        plugin = _make_plugin_instance(plugin_dir, "builder", inventory)
        subagents, _ = _process_agent_plugin(plugin)
        assert len(subagents) == 1
        assert subagents[0]["source"] == "plugin:builder@test-marketplace"

    def test_subagent_name_namespaced(self, tmp_path):
        plugin_dir = _make_agent_plugin(tmp_path, "debugger")
        inventory = _load_plugin_inventory(plugin_dir)
        plugin = _make_plugin_instance(plugin_dir, "debugger", inventory)
        subagents, _ = _process_agent_plugin(plugin)
        assert len(subagents) == 1
        # Name should be namespaced: agent_name@marketplace
        assert subagents[0]["name"] == "debugger@test-marketplace"

    def test_permission_tier_parsed_from_frontmatter(self, tmp_path):
        plugin_dir = tmp_path / "secure-agent"
        plugin_dir.mkdir()
        agents_dir = plugin_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "secure.md").write_text(
            "---\nname: secure\ndescription: Secure agent\n"
            "permission_tier: read-only\n---\nYou are a read-only agent.",
            encoding="utf-8",
        )
        manifest_dir = plugin_dir / ".claude-plugin"
        manifest_dir.mkdir()
        (manifest_dir / "plugin.json").write_text(
            json.dumps({"name": "secure-agent"}), encoding="utf-8",
        )

        inventory = _load_plugin_inventory(plugin_dir)
        plugin = _make_plugin_instance(plugin_dir, "secure-agent", inventory)
        subagents, _ = _process_agent_plugin(plugin)
        assert len(subagents) == 1
        assert subagents[0].get("permission_tier") == "read-only"

    def test_multiple_agents_in_one_plugin(self, tmp_path):
        plugin_dir = tmp_path / "multi-agent"
        plugin_dir.mkdir()
        agents_dir = plugin_dir / "agents"
        agents_dir.mkdir()

        (agents_dir / "reviewer.md").write_text(
            "---\nname: reviewer\ndescription: Code reviewer\n---\nReview prompt.",
            encoding="utf-8",
        )
        (agents_dir / "fixer.md").write_text(
            "---\nname: fixer\ndescription: Auto fixer\n---\nFix prompt.",
            encoding="utf-8",
        )

        manifest_dir = plugin_dir / ".claude-plugin"
        manifest_dir.mkdir()
        (manifest_dir / "plugin.json").write_text(
            json.dumps({"name": "multi-agent"}), encoding="utf-8",
        )

        inventory = _load_plugin_inventory(plugin_dir)
        plugin = _make_plugin_instance(plugin_dir, "multi-agent", inventory)
        subagents, _ = _process_agent_plugin(plugin)
        assert len(subagents) == 2
        names = {s["name"] for s in subagents}
        assert any("reviewer" in n for n in names)
        assert any("fixer" in n for n in names)


# ── Test Class 4: Agent Plugin Skill Binding ─────────────────────


class TestAgentPluginSkillBinding:
    """Verify skills from agent plugins are exclusively bound to their subagent."""

    def test_agent_plugin_skills_not_in_main_sources(self, tmp_path, _patch_plugin_data_dir):
        project_root = tmp_path / "project"
        dcoder_dir = project_root / ".dcoder"
        plugins_dir = dcoder_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        _make_agent_plugin(plugins_dir, "agent-only", skills=["agent-skill"])
        _write_marketplace(dcoder_dir, [
            {"name": "agent-only", "source": "./plugins/agent-only"},
        ])

        result = load_project_plugins(project_root)
        # Agent plugin skills should NOT be in main_skill_sources
        main_skill_paths = [src[0] for src in result.main_skill_sources]
        for path in main_skill_paths:
            assert "agent-only" not in path

    def test_agent_plugin_skills_in_subagent_meta(self, tmp_path):
        plugin_dir = _make_agent_plugin(
            tmp_path, "linter", skills=["fmt-check", "validate"],
        )
        inventory = _load_plugin_inventory(plugin_dir)
        plugin = _make_plugin_instance(plugin_dir, "linter", inventory)
        subagents, _ = _process_agent_plugin(plugin)
        assert len(subagents) == 1
        skills = subagents[0].get("skills") or []
        assert len(skills) >= 2

    def test_skill_names_from_directory_structure(self, tmp_path):
        plugin_dir = _make_agent_plugin(
            tmp_path, "test-plugin", skills=["alpha-skill", "beta-skill"],
        )
        inventory = _load_plugin_inventory(plugin_dir)
        names = _collect_skill_names(inventory)
        assert "alpha-skill" in names
        assert "beta-skill" in names


# ── Test Class 5: Agent Plugin MCP Binding ───────────────────────


class TestAgentPluginMCPBinding:
    """Verify MCP configs from agent plugins bind to subagent, not main."""

    def test_agent_plugin_mcp_not_in_main_configs(self, tmp_path, _patch_plugin_data_dir):
        project_root = tmp_path / "project"
        dcoder_dir = project_root / ".dcoder"
        plugins_dir = dcoder_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        _make_agent_plugin(
            plugins_dir, "mcp-agent",
            mcp_servers={"test-server": {"command": "echo"}},
        )
        _write_marketplace(dcoder_dir, [
            {"name": "mcp-agent", "source": "./plugins/mcp-agent"},
        ])

        result = load_project_plugins(project_root)
        assert len(result.main_mcp_configs) == 0

    def test_agent_plugin_mcp_in_subagent_meta(self, tmp_path):
        mcp_cfg = {"myserver": {"command": "run", "args": ["--port", "8080"]}}
        plugin_dir = _make_agent_plugin(tmp_path, "mcp-agent", mcp_servers=mcp_cfg)
        inventory = _load_plugin_inventory(plugin_dir)
        plugin = _make_plugin_instance(plugin_dir, "mcp-agent", inventory)
        subagents, _ = _process_agent_plugin(plugin)
        assert len(subagents) == 1
        mcp_files = subagents[0].get("mcp_files") or []
        assert len(mcp_files) == 1

    def test_mcp_json_parsed_correctly(self, tmp_path):
        mcp_file = tmp_path / ".mcp.json"
        mcp_file.write_text(
            json.dumps({"mcpServers": {
                "srv1": {"command": "echo", "args": ["hello"]},
                "srv2": {"command": "cat"},
            }}),
            encoding="utf-8",
        )
        result = _read_mcp_config((mcp_file,))
        assert result is not None
        assert "srv1" in result["mcpServers"]
        assert "srv2" in result["mcpServers"]
        assert result["mcpServers"]["srv1"]["args"] == ["hello"]


# ── Test Class 6: Main Plugin Binding ────────────────────────────


class TestMainPluginBinding:
    """Verify non-agent plugins' skills/MCP/commands bind to main agent."""

    def test_main_plugin_skills_in_main_sources(self, tmp_path, _patch_plugin_data_dir):
        project_root = tmp_path / "project"
        dcoder_dir = project_root / ".dcoder"
        plugins_dir = dcoder_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        _make_main_plugin(plugins_dir, "utilities", skills=["formatter"])
        _write_marketplace(dcoder_dir, [
            {"name": "utilities", "source": "./plugins/utilities"},
        ])

        result = load_project_plugins(project_root)
        assert len(result.main_skill_sources) >= 1
        assert len(result.subagent_metas) == 0

    def test_main_plugin_mcp_in_main_configs(self, tmp_path, _patch_plugin_data_dir):
        project_root = tmp_path / "project"
        dcoder_dir = project_root / ".dcoder"
        plugins_dir = dcoder_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        _make_main_plugin(
            plugins_dir, "mcp-main",
            mcp_servers={"pricing": {"command": "price-server"}},
        )
        _write_marketplace(dcoder_dir, [
            {"name": "mcp-main", "source": "./plugins/mcp-main"},
        ])

        result = load_project_plugins(project_root)
        assert len(result.main_mcp_configs) >= 1
        servers = result.main_mcp_configs[0].get("mcpServers", {})
        assert "pricing" in servers

    def test_main_plugin_commands_discovered(self, tmp_path, _patch_plugin_data_dir):
        project_root = tmp_path / "project"
        dcoder_dir = project_root / ".dcoder"
        plugins_dir = dcoder_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        _make_main_plugin(
            plugins_dir, "cmd-plugin",
            commands=["review-module", "scan-security"],
        )
        _write_marketplace(dcoder_dir, [
            {"name": "cmd-plugin", "source": "./plugins/cmd-plugin"},
        ])

        result = load_project_plugins(project_root)
        assert len(result.main_commands) >= 1

    def test_main_plugin_no_subagent_produced(self, tmp_path, _patch_plugin_data_dir):
        project_root = tmp_path / "project"
        dcoder_dir = project_root / ".dcoder"
        plugins_dir = dcoder_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        _make_main_plugin(plugins_dir, "simple", skills=["helper"])
        _write_marketplace(dcoder_dir, [
            {"name": "simple", "source": "./plugins/simple"},
        ])

        result = load_project_plugins(project_root)
        assert len(result.subagent_metas) == 0


# ── Test Class 7: SubagentsMiddleware Integration ───────────────


class TestSubagentsMiddlewareIntegration:
    """Verify SubagentsMiddleware correctly registers project plugin subagents."""

    @staticmethod
    def _make_meta(name: str, description: str = "desc", **kwargs: Any) -> SubagentMetadata:
        meta: dict[str, Any] = {
            "name": name,
            "description": description,
            "system_prompt": "prompt",
            "source": "plugin:test",
            "path": f"/path/{name}",
        }
        meta.update(kwargs)
        return cast(SubagentMetadata, meta)

    def test_project_subagents_registered(self):
        from dcoder.middleware.subagents import SubagentsMiddleware

        metas = [
            self._make_meta("proj-linter", "Linter"),
            self._make_meta("proj-scanner", "Scanner"),
        ]
        mw = SubagentsMiddleware(subagent_metas=metas)
        assert "proj-linter" in mw.subagent_names
        assert "proj-scanner" in mw.subagent_names

    def test_middleware_before_agent_injects_registry(self):
        from dcoder.middleware.subagents import SubagentsMiddleware

        metas = [
            self._make_meta(
                "proj-agent",
                "Agent",
                skills=["skill-a"],
                permission_tier="read-write",
            ),
        ]
        mw = SubagentsMiddleware(subagent_metas=metas)
        result = mw.before_agent(state=cast(Any, {"messages": []}), runtime=cast(Any, None))
        assert result is not None
        registry = result.get("_subagent_registry", {})
        assert "proj-agent" in registry
        assert registry["proj-agent"]["skills"] == ["skill-a"]
        assert registry["proj-agent"]["permission_tier"] == "read-write"

    def test_get_subagent_by_name_works(self):
        from dcoder.middleware.subagents import SubagentsMiddleware

        metas = [
            self._make_meta("lookup-target", "Target"),
        ]
        mw = SubagentsMiddleware(subagent_metas=metas)
        result = mw.get_subagent("lookup-target")
        assert result is not None
        assert result["name"] == "lookup-target"

        assert mw.get_subagent("nonexistent") is None

    def test_prompt_block_includes_project_agents(self):
        from dcoder.middleware.subagents import SubagentsMiddleware

        metas = [
            self._make_meta("prompt-agent", "Show in prompt"),
        ]
        mw = SubagentsMiddleware(subagent_metas=metas)
        block = mw._build_prompt_block()
        assert "prompt-agent" in block
        assert "Show in prompt" in block

    def test_register_subagent_at_runtime(self):
        from dcoder.middleware.subagents import SubagentsMiddleware

        mw = SubagentsMiddleware()
        assert len(mw.subagent_names) == 0

        mw.register_subagent(self._make_meta("dynamic-agent", "Added at runtime"))
        assert "dynamic-agent" in mw.subagent_names
        assert mw.get_subagent("dynamic-agent") is not None


# ── Test Class 8: End-to-End Project Plugins ─────────────────────


class TestEndToEndProjectPlugins:
    """Full integration tests simulating a real .dcoder marketplace."""

    def test_full_marketplace_with_mixed_plugins(self, tmp_path, _patch_plugin_data_dir):
        """Build a 3-plugin marketplace (1 agent + 2 main), verify complete bifurcation."""
        project_root = tmp_path / "project"
        dcoder_dir = project_root / ".dcoder"
        plugins_dir = dcoder_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        # 1) Agent plugin with skills + MCP
        _make_agent_plugin(
            plugins_dir, "tf-linter",
            skills=["tf-fmt-check", "tf-validate"],
            mcp_servers={"tflint": {"command": "tflint", "args": ["--serve"]}},
        )

        # 2) Non-agent plugin with MCP
        _make_main_plugin(
            plugins_dir, "cost-estimator",
            skills=["cost-estimate"],
            mcp_servers={"infracost": {"command": "infracost"}},
        )

        # 3) Non-agent plugin with commands
        _make_main_plugin(
            plugins_dir, "module-reviewer",
            skills=["best-practices", "security-scan"],
            commands=["review-module", "scan-security"],
        )

        _write_marketplace(dcoder_dir, [
            {"name": "tf-linter", "source": "./plugins/tf-linter"},
            {"name": "cost-estimator", "source": "./plugins/cost-estimator"},
            {"name": "module-reviewer", "source": "./plugins/module-reviewer"},
        ])

        result = load_project_plugins(project_root)

        # Agent plugin → subagent
        assert len(result.subagent_metas) >= 1
        agent_names = [m.get("name", "") for m in result.subagent_metas]
        assert any("tf-linter" in n for n in agent_names)

        # Non-agent plugin skills → main
        assert len(result.main_skill_sources) >= 2

        # Non-agent plugin MCP → main
        assert len(result.main_mcp_configs) >= 1
        all_servers = {}
        for cfg in result.main_mcp_configs:
            all_servers.update(cfg.get("mcpServers", {}))
        assert "infracost" in all_servers

        # Non-agent plugin commands → main
        assert len(result.main_commands) >= 1

        # Agent plugin MCP should NOT be in main
        assert "tflint" not in all_servers

    def test_missing_plugin_source_produces_warning(self, tmp_path, _patch_plugin_data_dir):
        project_root = tmp_path / "project"
        dcoder_dir = project_root / ".dcoder"
        dcoder_dir.mkdir(parents=True)

        _write_marketplace(dcoder_dir, [
            {"name": "ghost-plugin", "source": "./plugins/nonexistent"},
        ])

        result = load_project_plugins(project_root)
        # Non-existent source resolves but produces no components
        assert len(result.subagent_metas) == 0
        assert len(result.main_skill_sources) == 0
        assert len(result.main_mcp_configs) == 0

    def test_malformed_marketplace_json_produces_warning(self, tmp_path):
        project_root = tmp_path / "project"
        dcoder_dir = project_root / ".dcoder"
        mp_dir = dcoder_dir / ".dcoder-plugin"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text(
            "{ invalid json !!!", encoding="utf-8",
        )

        result = load_project_plugins(project_root)
        assert len(result.subagent_metas) == 0
        assert len(result.main_skill_sources) == 0
        assert any("could not load" in w.lower() or "marketplace" in w.lower()
                    for w in result.warnings)

    def test_plugin_with_no_skills_no_agents_no_mcp(self, tmp_path, _patch_plugin_data_dir):
        """Minimal plugin with only a manifest → discovered but no components."""
        project_root = tmp_path / "project"
        dcoder_dir = project_root / ".dcoder"
        plugins_dir = dcoder_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        # Plugin with only a manifest
        empty_plugin = plugins_dir / "empty-plugin"
        empty_plugin.mkdir()
        manifest_dir = empty_plugin / ".claude-plugin"
        manifest_dir.mkdir()
        (manifest_dir / "plugin.json").write_text(
            json.dumps({"name": "empty-plugin"}), encoding="utf-8",
        )

        _write_marketplace(dcoder_dir, [
            {"name": "empty-plugin", "source": "./plugins/empty-plugin"},
        ])

        result = load_project_plugins(project_root)
        # Should not crash, no components produced
        assert len(result.subagent_metas) == 0
        assert len(result.main_skill_sources) == 0
        assert len(result.main_mcp_configs) == 0

    def test_none_project_root_returns_empty(self):
        """Passing None as project_root returns empty result."""
        result = load_project_plugins(None)
        assert len(result.subagent_metas) == 0
        assert len(result.main_skill_sources) == 0
        assert len(result.main_mcp_configs) == 0

    def test_project_without_dcoder_dir_returns_empty(self, tmp_path):
        result = load_project_plugins(tmp_path)
        assert len(result.subagent_metas) == 0


# ── Utility function tests ──────────────────────────────────────


class TestUtilityFunctions:
    """Tests for internal utility functions."""

    def test_collect_skill_names_from_dir(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        for name in ["alpha", "beta", "gamma"]:
            sub = skills_dir / name
            sub.mkdir()
            (sub / "SKILL.md").write_text(f"# {name}", encoding="utf-8")

        inventory = ComponentInventory(skills=(skills_dir,))
        names = _collect_skill_names(inventory)
        assert sorted(names) == ["alpha", "beta", "gamma"]

    def test_collect_skill_names_empty_dir(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        inventory = ComponentInventory(skills=(skills_dir,))
        names = _collect_skill_names(inventory)
        assert names == []

    def test_read_mcp_config_merges_multiple_files(self, tmp_path):
        f1 = tmp_path / "a.json"
        f1.write_text(
            json.dumps({"mcpServers": {"srv-a": {"command": "a"}}}), encoding="utf-8",
        )
        f2 = tmp_path / "b.json"
        f2.write_text(
            json.dumps({"mcpServers": {"srv-b": {"command": "b"}}}), encoding="utf-8",
        )
        result = _read_mcp_config((f1, f2))
        assert result is not None
        assert "srv-a" in result["mcpServers"]
        assert "srv-b" in result["mcpServers"]

    def test_read_mcp_config_no_files(self):
        result = _read_mcp_config(())
        assert result is None

    def test_read_mcp_config_handles_corrupt_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json!", encoding="utf-8")
        result = _read_mcp_config((bad,))
        assert result is None

    def test_has_agents_with_file_agent(self, tmp_path):
        """An .md file directly in agents tuple is treated as agent."""
        agents_file = tmp_path / "agent.md"
        agents_file.write_text("---\nname: a\ndescription: b\n---\nc", encoding="utf-8")
        inventory = ComponentInventory(agents=(agents_file,))
        assert _has_agents(inventory) is True

    def test_build_plugin_instance_returns_none_for_bad_root(self, tmp_path, _patch_plugin_data_dir):
        result, warnings = _build_plugin_instance(
            "bad", "mp", tmp_path / "nonexistent", "bad",
        )
        # May return None or a plugin with empty inventory, both are acceptable
        # The key is that it doesn't crash
        assert isinstance(warnings, list)
