from typing import Any, cast
import pytest
from pathlib import Path
from opscode.subagents.loader import SubagentMetadata, _parse_subagent_file
from opscode.plugins.adapters.agents import _enrich_plugin_subagent
from opscode.plugins.models import ComponentInventory, PluginInstance
from opscode.agent.factory import _subagent_cli_middleware

def test_parse_subagent_rich_frontmatter(tmp_path):
    subagent_file = tmp_path / "AGENTS.md"
    subagent_file.write_text(
        "---\n"
        "name: earnings-reviewer\n"
        "description: Expert earnings reviewer\n"
        "model: anthropic:claude-3-5-sonnet\n"
        "skills:\n"
        "  - earnings-analysis\n"
        "tools:\n"
        "  - read_file\n"
        "  - mcp__financial__*\n"
        "mcp_config:\n"
        "  mcpServers:\n"
        "    financial:\n"
        "      command: uvx\n"
        "      args: ['mcp-server-financial']\n"
        "---\n"
        "System prompt for earnings reviewer.",
        encoding="utf-8"
    )

    metadata = _parse_subagent_file(subagent_file)
    assert metadata is not None
    assert metadata["name"] == "earnings-reviewer"
    assert metadata["description"] == "Expert earnings reviewer"
    assert metadata.get("skills") == ["earnings-analysis"]
    assert metadata.get("tools") == ["read_file", "mcp__financial__*"]
    assert metadata.get("mcp_config") == {
        "mcpServers": {
            "financial": {
                "command": "uvx",
                "args": ["mcp-server-financial"],
            }
        }
    }


def test_plugin_subagent_enrichment(tmp_path):
    mcp_file = tmp_path / ".mcp.json"
    mcp_file.write_text('{"mcpServers": {"server1": {"command": "echo"}}}', encoding="utf-8")

    plugin = PluginInstance(
        plugin_id="earnings-reviewer@official",
        name="earnings-reviewer",
        marketplace="official",
        version="0.1.0",
        root=tmp_path,
        data_dir=tmp_path / "data",
        manifest=None,
        inventory=ComponentInventory(mcp_files=(mcp_file,)),
    )

    meta: SubagentMetadata = {
        "name": "reviewer",
        "description": "Reviewer",
        "system_prompt": "Prompt",
        "source": "",
        "path": str(tmp_path / "AGENTS.md"),
    }

    enriched = _enrich_plugin_subagent(meta, plugin)
    assert enriched["name"] == "earnings-reviewer@official:reviewer"
    assert enriched["source"] == "plugin:earnings-reviewer@official"
    assert enriched.get("skills") == ["earnings-reviewer@official:*"]
    assert enriched.get("mcp_files") == [str(mcp_file)]


def test_subagent_cli_middleware_custom_skills(tmp_path):
    agents_dir = tmp_path / "earnings-reviewer"
    skills_dir = agents_dir / "skills" / "earnings-analysis"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: earnings-analysis\ndescription: Analysis skill\n---\nBody", encoding="utf-8"
    )

    agents_file = agents_dir / "AGENTS.md"
    agents_file.write_text(
        "---\nname: earnings-reviewer\ndescription: Reviewer\n---\nPrompt", encoding="utf-8"
    )

    middleware_stack = _subagent_cli_middleware(
        has_explicit_model=True,
        assistant_id="test_agent",
        subagent_name="earnings-reviewer",
        allowed_skills=["earnings-analysis"],
        interactive=True,
        subagent_path=str(agents_file),
    )

    assert len(middleware_stack) > 0


def test_subagent_local_skills_resolution(tmp_path):
    from opscode.middleware.skills import PluginSkillsMiddleware

    bundle_dir = tmp_path / "terraform-reviewer"
    agents_dir = bundle_dir / "agents"
    agents_dir.mkdir(parents=True)

    agent_file = agents_dir / "terraform-reviewer.md"
    agent_file.write_text(
        "---\nname: terraform-reviewer\ndescription: Reviewer\n---\nPrompt",
        encoding="utf-8",
    )

    skill1_dir = bundle_dir / "skills" / "terraform-lock-audit"
    skill1_dir.mkdir(parents=True)
    (skill1_dir / "SKILL.md").write_text(
        "---\nname: terraform-lock-audit\ndescription: Lock audit\n---\nBody 1",
        encoding="utf-8",
    )

    middleware_stack = _subagent_cli_middleware(
        has_explicit_model=True,
        assistant_id="test_agent",
        subagent_name="terraform-reviewer",
        allowed_skills=["terraform-lock-audit"],
        interactive=True,
        subagent_path=str(agent_file),
    )

    skills_mw = next(m for m in middleware_stack if isinstance(m, PluginSkillsMiddleware))
    res = cast(Any, skills_mw).before_agent(state={"messages": []}, runtime=None, config=None)
    assert res is not None
    loaded_names = [s["name"] for s in res.get("skills_metadata", [])]
    assert "terraform-lock-audit" in loaded_names

