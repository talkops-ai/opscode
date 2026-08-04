import pytest
from pathlib import Path
from dcoder.subagents.loader import _parse_subagent_file, list_subagents
from dcoder.subagents.devops_subagents import get_built_in_subagents

def test_parse_subagent_file(tmp_path):
    subagent_file = tmp_path / "AGENTS.md"
    subagent_file.write_text(
        "---\n"
        "name: test-reviewer\n"
        "description: Review code style and conventions\n"
        "model: anthropic:claude-haiku\n"
        "---\n"
        "You are a code style reviewer assistant.",
        encoding="utf-8"
    )
    
    metadata = _parse_subagent_file(subagent_file)
    assert metadata is not None
    assert metadata["name"] == "test-reviewer"
    assert metadata["description"] == "Review code style and conventions"
    assert metadata.get("model") == "anthropic:claude-haiku"
    assert metadata["system_prompt"] == "You are a code style reviewer assistant."

def test_parse_subagent_fallback_name(tmp_path):
    subagent_file = tmp_path / "AGENTS.md"
    subagent_file.write_text(
        "---\n"
        "description: Review code style\n"
        "---\n"
        "System prompt body.",
        encoding="utf-8"
    )
    
    # Missing name should fallback to the specified name (directory name)
    metadata = _parse_subagent_file(subagent_file, fallback_name="dir-name")
    assert metadata is not None
    assert metadata["name"] == "dir-name"
    assert metadata["description"] == "Review code style"

def test_built_in_subagents():
    built_ins = get_built_in_subagents()
    assert len(built_ins) == 3
    names = [s["name"] for s in built_ins]
    assert "terraform-reviewer" in names
    assert "helm-validator" in names
    assert "k8s-auditor" in names
    
    # Ensure prompts contain essential instructions
    tf_reviewer = next(s for s in built_ins if s["name"] == "terraform-reviewer")
    assert "vulnerabilities" in tf_reviewer["description"].lower()
    assert "state declarations" in tf_reviewer["system_prompt"].lower()
