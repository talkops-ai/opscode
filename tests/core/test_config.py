import os
from pathlib import Path
from unittest.mock import patch
import pytest

from dcoder.config.settings import resolve_env_var, Settings, _load_dotenv
from dcoder.config.manifest import ENV_PREFIX, DOTENV_DENIED_ENV_KEYS

def test_resolve_env_var():
    with patch.dict(os.environ, {"DCODER_TEST_VAR": "prefixed", "TEST_VAR": "plain"}):
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
    assert s.get_user_skills_dir("dcoder") == s.user_dcoder_dir / "dcoder" / "skills"
    assert s.get_project_skills_dir() == Path("/fake/project") / ".dcoder" / "skills"
