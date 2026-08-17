import os
from pathlib import Path
from unittest.mock import patch
import pytest

from opscode.config.settings import resolve_env_var, Settings, _load_dotenv
from opscode.config.manifest import ENV_PREFIX, DOTENV_DENIED_ENV_KEYS

def test_resolve_env_var():
    with patch.dict(os.environ, {"OPSCODE_TEST_VAR": "prefixed", "TEST_VAR": "plain"}):
        assert resolve_env_var("TEST_VAR") == "prefixed"
        
    with patch.dict(os.environ, {"TEST_VAR": "plain"}):
        if f"{ENV_PREFIX}TEST_VAR" in os.environ:
            del os.environ[f"{ENV_PREFIX}TEST_VAR"]
        assert resolve_env_var("TEST_VAR") == "plain"
        
    with patch.dict(os.environ, {"TEST_VAR": ""}):
        if f"{ENV_PREFIX}TEST_VAR" in os.environ:
            del os.environ[f"{ENV_PREFIX}TEST_VAR"]
        assert resolve_env_var("TEST_VAR") is None


def test_dotenv_denylist(tmp_path):
    dotenv_content = "PATH=/usr/bin/hijacked\nOPENAI_API_KEY=testkey\n"
    env_file = tmp_path / ".env"
    env_file.write_text(dotenv_content)
    
    with patch.dict(os.environ, {}, clear=True):
        _load_dotenv(start_path=tmp_path)
        assert "OPENAI_API_KEY" in os.environ
        assert os.environ["OPENAI_API_KEY"] == "testkey"
        assert "PATH" not in os.environ  # Denied key should not be loaded from dotenv


def test_settings_path_helpers():
    s = Settings(project_root=Path("/fake/project"))
    assert s.get_user_skills_dir("opscode") == s.user_opscode_dir / "opscode" / "skills"
    assert s.get_project_skills_dir() == Path("/fake/project") / ".opscode" / "skills"


def test_upsert_env_vars(tmp_path):
    from opscode.config.paths import upsert_env_vars

    env_file = tmp_path / ".env"
    initial_content = (
        "# Global environment credentials\n"
        "GOOGLE_API_KEY=old_key_1\n"
        "GOOGLE_GENAI_USE_VERTEXAI=true\n"
        "\n"
        "LANGSMITH_API_KEY=ls_key_1\n"
        "GOOGLE_API_KEY=old_key_2\n"
        "GOOGLE_GENAI_USE_VERTEXAI=true\n"
    )
    env_file.write_text(initial_content, encoding="utf-8")

    # Perform upsert
    new_vars = {
        "GOOGLE_API_KEY": "new_google_key",
        "GOOGLE_GENAI_USE_VERTEXAI": "false",
        "ANTHROPIC_API_KEY": "new_anthropic_key",
    }
    assert upsert_env_vars(new_vars, env_path=env_file)

    result_content = env_file.read_text(encoding="utf-8")
    lines = [line for line in result_content.splitlines() if line]

    assert "# Global environment credentials" in lines
    assert "GOOGLE_API_KEY=new_google_key" in lines
    assert "GOOGLE_GENAI_USE_VERTEXAI=false" in lines
    assert "LANGSMITH_API_KEY=ls_key_1" in lines
    assert "ANTHROPIC_API_KEY=new_anthropic_key" in lines

    # Verify deduplication: GOOGLE_API_KEY and GOOGLE_GENAI_USE_VERTEXAI appear exactly once
    assert lines.count("GOOGLE_API_KEY=new_google_key") == 1
    assert lines.count("GOOGLE_GENAI_USE_VERTEXAI=false") == 1
    assert not any("old_key" in l for l in lines)

