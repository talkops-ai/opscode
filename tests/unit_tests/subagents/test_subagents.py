import pytest
from pathlib import Path
from dcoder.subagents.loader import _parse_subagent_file, list_subagents
from dcoder.subagents import get_built_in_subagents

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
    assert len(built_ins) >= 3
    names = [s["name"] for s in built_ins]
    assert "aws-terraform-writer" in names
    assert "k8s-helm-provisioner" in names
    assert "infra-ansible-provisioner" in names
    
    # Ensure prompts contain essential instructions
    aws_tf = next(s for s in built_ins if s["name"] == "aws-terraform-writer")
    assert len(aws_tf["description"]) > 0
    assert len(aws_tf["system_prompt"]) > 0


def test_load_async_subagents(tmp_path):
    from dcoder.subagents.loader import load_async_subagents

    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[async_subagents.remote_researcher]\n'
        'description = "Remote research subagent"\n'
        'graph_id = "agent"\n'
        'url = "https://my-deployment.langsmith.dev"\n'
        'headers = { "Authorization" = "Bearer secret" }\n',
        encoding="utf-8",
    )

    async_subs = load_async_subagents(config_file)
    assert len(async_subs) == 1
    assert async_subs[0]["name"] == "remote_researcher"
    assert async_subs[0]["description"] == "Remote research subagent"
    assert async_subs[0]["graph_id"] == "agent"
    assert async_subs[0]["url"] == "https://my-deployment.langsmith.dev"
    assert async_subs[0]["headers"] == {"Authorization": "Bearer secret"}


def test_load_async_subagents_missing_fields(tmp_path, caplog):
    from dcoder.subagents.loader import load_async_subagents

    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[async_subagents.invalid_sub]\n'
        'url = "https://my-deployment.langsmith.dev"\n',
        encoding="utf-8",
    )

    with caplog.at_level("WARNING"):
        async_subs = load_async_subagents(config_file)
        assert len(async_subs) == 0
        assert "Skipping async subagent 'invalid_sub'" in caplog.text


def test_subagent_directory_stray_file_warning(tmp_path, caplog):
    from dcoder.subagents.loader import list_subagents

    # Create a stray file directly in agents dir
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "stray.md").write_text("Not in folder", encoding="utf-8")

    with caplog.at_level("WARNING"):
        subs = list_subagents(user_agents_dir=agents_dir, include_plugins=False)
        assert len(subs) == 0
        assert "Ignoring user subagent file" in caplog.text


def test_subagent_folder_missing_agents_md(tmp_path, caplog):
    from dcoder.subagents.loader import list_subagents

    agents_dir = tmp_path / "agents"
    sub_dir = agents_dir / "my_subagent"
    sub_dir.mkdir(parents=True)
    (sub_dir / "readme.md").write_text("Wrong filename", encoding="utf-8")

    with caplog.at_level("WARNING"):
        subs = list_subagents(user_agents_dir=agents_dir, include_plugins=False)
        assert len(subs) == 0
        assert "expected an AGENTS.md file" in caplog.text


def test_subagent_invalid_frontmatter_fields(tmp_path, caplog):
    from dcoder.subagents.loader import _parse_subagent_file

    file_path = tmp_path / "AGENTS.md"
    file_path.write_text(
        "---\n"
        "name: ''\n"
        "---\n"
        "Body text",
        encoding="utf-8",
    )

    with caplog.at_level("WARNING"):
        metadata = _parse_subagent_file(file_path)
        assert metadata is None
        assert "invalid or missing frontmatter field(s)" in caplog.text


def test_subagent_name_collision(tmp_path, caplog):
    from dcoder.subagents.loader import list_subagents

    agents_dir = tmp_path / "agents"
    sub1 = agents_dir / "sub1"
    sub1.mkdir(parents=True)
    (sub1 / "AGENTS.md").write_text(
        "---\nname: duplicate-name\ndescription: Sub 1\n---\nPrompt 1", encoding="utf-8"
    )

    sub2 = agents_dir / "sub2"
    sub2.mkdir(parents=True)
    (sub2 / "AGENTS.md").write_text(
        "---\nname: duplicate-name\ndescription: Sub 2\n---\nPrompt 2", encoding="utf-8"
    )

    with caplog.at_level("WARNING"):
        subs = list_subagents(user_agents_dir=agents_dir, include_plugins=False)
        assert len(subs) == 1
        assert "Subagent name collision" in caplog.text


def test_parse_subagent_with_permission_tier(tmp_path):
    """Frontmatter `permission_tier: read-only` is parsed into metadata."""
    subagent_file = tmp_path / "AGENTS.md"
    subagent_file.write_text(
        "---\n"
        "name: secure-agent\n"
        "description: Read-only agent\n"
        "permission_tier: read-only\n"
        "---\n"
        "You only observe.",
        encoding="utf-8",
    )

    metadata = _parse_subagent_file(subagent_file)
    assert metadata is not None
    assert metadata["name"] == "secure-agent"
    assert metadata.get("permission_tier") == "read-only"


def test_parse_subagent_with_skills_and_tools(tmp_path):
    """Frontmatter `skills:` and `tools:` lists are parsed."""
    subagent_file = tmp_path / "AGENTS.md"
    subagent_file.write_text(
        "---\n"
        "name: full-agent\n"
        "description: Agent with skills and tools\n"
        "skills:\n"
        "  - skill-alpha\n"
        "  - skill-beta\n"
        "tools:\n"
        "  - read_file\n"
        "  - write_file\n"
        "  - mcp__server__*\n"
        "---\n"
        "Full-featured agent.",
        encoding="utf-8",
    )

    metadata = _parse_subagent_file(subagent_file)
    assert metadata is not None
    assert metadata.get("skills") == ["skill-alpha", "skill-beta"]
    assert metadata.get("tools") == ["read_file", "write_file", "mcp__server__*"]


def test_parse_subagent_with_mcp_config(tmp_path):
    """Frontmatter `mcp_config:` dict is parsed."""
    subagent_file = tmp_path / "AGENTS.md"
    subagent_file.write_text(
        "---\n"
        "name: mcp-agent\n"
        "description: Agent with MCP\n"
        "mcp_config:\n"
        "  mcpServers:\n"
        "    myserver:\n"
        "      command: run\n"
        "---\n"
        "MCP-powered agent.",
        encoding="utf-8",
    )

    metadata = _parse_subagent_file(subagent_file)
    assert metadata is not None
    mcp_config = metadata.get("mcp_config")
    assert mcp_config is not None
    assert "myserver" in (mcp_config.get("mcpServers") or {})


def test_parse_subagent_with_mcp_files(tmp_path):
    """Frontmatter `mcp_files:` list is parsed."""
    subagent_file = tmp_path / "AGENTS.md"
    subagent_file.write_text(
        "---\n"
        "name: files-agent\n"
        "description: Agent with MCP files\n"
        "mcp_files:\n"
        "  - /path/to/.mcp.json\n"
        "---\n"
        "Files-based agent.",
        encoding="utf-8",
    )

    metadata = _parse_subagent_file(subagent_file)
    assert metadata is not None
    assert metadata.get("mcp_files") == ["/path/to/.mcp.json"]


def test_parse_subagent_comma_separated_skills(tmp_path):
    """Skills specified as a comma-separated string are parsed."""
    subagent_file = tmp_path / "AGENTS.md"
    subagent_file.write_text(
        "---\n"
        "name: csv-agent\n"
        "description: CSV skills\n"
        "skills: alpha, beta, gamma\n"
        "---\n"
        "CSV prompt.",
        encoding="utf-8",
    )

    metadata = _parse_subagent_file(subagent_file)
    assert metadata is not None
    assert metadata.get("skills") == ["alpha", "beta", "gamma"]

