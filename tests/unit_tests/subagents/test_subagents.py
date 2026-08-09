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

