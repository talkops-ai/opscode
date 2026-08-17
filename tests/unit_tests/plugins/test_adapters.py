import pytest
from pathlib import Path
from opscode.plugins.models import ComponentInventory, PluginInstance
from opscode.plugins.adapters.agents import plugin_subagents
from opscode.plugins.adapters.commands import plugin_commands


def test_plugin_subagents_adapter(tmp_path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    agent_file = agents_dir / "debugger.md"
    agent_file.write_text(
        "---\nname: debugger\ndescription: Plugin debugger agent\ntools:\n  - read_file\nskills:\n  - common-devops:log-analyzer\n---\n\nYou are a debugger.",
        encoding="utf-8",
    )

    inventory = ComponentInventory(agents=(agents_dir,))
    plugin = PluginInstance(
        plugin_id="test-pack@official",
        name="test-pack",
        marketplace="official",
        version="1.0.0",
        root=tmp_path,
        data_dir=tmp_path / "data",
        manifest=None,
        inventory=inventory,
    )

    subagents = plugin_subagents((plugin,))
    assert len(subagents) == 1
    assert subagents[0]["name"] == "test-pack@official:debugger"
    assert subagents[0].get("tools") == ["read_file"]
    assert subagents[0].get("skills") == ["common-devops:log-analyzer"]


def test_plugin_commands_adapter(tmp_path):
    commands_dir = tmp_path / "commands"
    commands_dir.mkdir()
    cmd_file = commands_dir / "audit.md"
    cmd_file.write_text("# Audit Command\nRun security audit.", encoding="utf-8")

    inventory = ComponentInventory(commands=(commands_dir,))
    plugin = PluginInstance(
        plugin_id="test-pack@official",
        name="test-pack",
        marketplace="official",
        version="1.0.0",
        root=tmp_path,
        data_dir=tmp_path / "data",
        manifest=None,
        inventory=inventory,
    )

    handlers = plugin_commands((plugin,))
    assert len(handlers) == 1
    assert handlers[0].name == "/audit"
    assert "/test-pack:audit" in handlers[0].aliases
