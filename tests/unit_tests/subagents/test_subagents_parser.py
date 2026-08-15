import pytest
from pathlib import Path
from dcoder.subagents.subagents_parser import parse_built_in_subagents, parse_subagent_bundle

def test_parse_built_in_subagents():
    built_ins = parse_built_in_subagents()
    assert len(built_ins) >= 3
    names = [b["name"] for b in built_ins]
    assert "aws-terraform-writer" in names
    assert "k8s-helm-provisioner" in names
    assert "infra-ansible-provisioner" in names

    aws_tf = next(b for b in built_ins if b["name"] == "aws-terraform-writer")
    assert aws_tf["source"] == "built-in"
    assert len(aws_tf["description"]) > 0

    helm = next(b for b in built_ins if b["name"] == "k8s-helm-provisioner")
    assert helm["source"] == "built-in"


def test_parse_subagent_bundle_custom(tmp_path):
    bundle_dir = tmp_path / "custom-agent"
    agents_dir = bundle_dir / "agents"
    agents_dir.mkdir(parents=True)

    agent_file = agents_dir / "custom-agent.md"
    agent_file.write_text(
        "---\n"
        "name: custom-agent\n"
        "description: Custom agent bundle\n"
        "skills:\n"
        "  - custom-skill\n"
        "---\n"
        "Custom prompt.",
        encoding="utf-8"
    )

    skills_dir = bundle_dir / "skills" / "custom-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: custom-skill\ndescription: Custom skill\n---\nSkill body",
        encoding="utf-8"
    )

    mcp_file = bundle_dir / ".mcp.json"
    mcp_file.write_text('{"mcpServers": {}}', encoding="utf-8")

    subagents = parse_subagent_bundle(bundle_dir, source="test")
    assert len(subagents) == 1
    sa = subagents[0]
    assert sa["name"] == "custom-agent"
    assert sa["description"] == "Custom agent bundle"
    assert sa["source"] == "test"
    assert sa.get("mcp_files") == [str(mcp_file)]
