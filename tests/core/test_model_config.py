import pytest
from pathlib import Path
from unittest.mock import patch

from dcoder.exceptions import ModelConfigError
from dcoder.model.config import ModelSpec, ModelConfig, get_provider_auth_status, ProviderAuthState

def test_model_spec_parse():
    spec = ModelSpec.parse("anthropic:claude-3-5-sonnet")
    assert spec.provider == "anthropic"
    assert spec.model == "claude-3-5-sonnet"
    assert str(spec) == "anthropic:claude-3-5-sonnet"

    with pytest.raises(ValueError):
        ModelSpec.parse("no-colon-spec")

    assert ModelSpec.try_parse("no-colon-spec") is None


def test_model_config_toml_load(tmp_path):
    config_toml = """
[models]
default = "anthropic:claude-3"

[models.providers.ollama]
enabled = true
models = ["qwen3:4b"]
base_url = "http://localhost:11434"
params = { temperature = 0.2 }
"""
    config_file = tmp_path / "config.toml"
    config_file.write_text(config_toml)

    mcfg = ModelConfig.load(config_path=config_file)
    assert mcfg.default_model == "anthropic:claude-3"
    assert mcfg.is_provider_enabled("ollama") is True
    assert mcfg.get_base_url("ollama") == "http://localhost:11434"
    assert mcfg.get_kwargs("ollama") == {"temperature": 0.2}


def test_auth_status():
    with patch("dcoder.model.config.resolve_env_var") as mock_resolve:
        mock_resolve.return_value = "my-key"
        status = get_provider_auth_status("openai")
        assert status.state == ProviderAuthState.CONFIGURED
        assert status.env_var == "OPENAI_API_KEY"
        assert status.as_legacy_bool() is True

        mock_resolve.return_value = None
        status = get_provider_auth_status("openai")
        assert status.state == ProviderAuthState.MISSING
        assert status.as_legacy_bool() is False
