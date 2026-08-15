import os
import tomllib
from pathlib import Path
import pytest

from opscode.config.toml_config import (
    clear_default_agent,
    clear_default_model,
    clear_effort_for_model,
    load_default_agent,
    load_default_model,
    load_effort_for_model,
    load_recent_agent,
    load_recent_model,
    load_theme_preference,
    save_default_agent,
    save_default_model,
    save_effort_for_model,
    save_recent_agent,
    save_recent_model,
    save_theme_preference,
)
from opscode.commands.core.model import ModelHandler
from opscode.commands.core.effort import EffortHandler
from opscode.commands._base import CommandContext


@pytest.fixture
def test_config_path(tmp_path):
    return tmp_path / "config.toml"


def test_models_section_persistence(test_config_path):
    assert save_recent_model("google_genai:gemini-3.6-flash", config_path=test_config_path)
    assert load_recent_model(config_path=test_config_path) == "google_genai:gemini-3.6-flash"

    assert save_default_model("openrouter:moonshotai/kimi-k3", config_path=test_config_path)
    assert load_default_model(config_path=test_config_path) == "openrouter:moonshotai/kimi-k3"
    # Recents should still be present
    assert load_recent_model(config_path=test_config_path) == "google_genai:gemini-3.6-flash"

    # Verify TOML contents directly
    with test_config_path.open("rb") as f:
        data = tomllib.load(f)
    assert data["models"]["recent"] == "google_genai:gemini-3.6-flash"
    assert data["models"]["default"] == "openrouter:moonshotai/kimi-k3"

    # Test clear_default_model
    assert clear_default_model(config_path=test_config_path)
    assert load_default_model(config_path=test_config_path) == "google_genai:gemini-3.6-flash" # Fallback to recent

    with test_config_path.open("rb") as f:
        data_after = tomllib.load(f)
    assert "default" not in data_after.get("models", {})
    assert data_after["models"]["recent"] == "google_genai:gemini-3.6-flash"


def test_effort_section_persistence(test_config_path):
    m1 = "google_genai:gemini-3.1-pro-preview"
    m2 = "google_genai:gemini-3.6-flash"

    assert save_effort_for_model(m1, "high", config_path=test_config_path)
    assert save_effort_for_model(m2, "medium", config_path=test_config_path)

    assert load_effort_for_model(m1, config_path=test_config_path) == "high"
    assert load_effort_for_model(m2, config_path=test_config_path) == "medium"

    # Clear one effort
    assert clear_effort_for_model(m1, config_path=test_config_path)
    assert load_effort_for_model(m1, config_path=test_config_path) is None
    assert load_effort_for_model(m2, config_path=test_config_path) == "medium"


def test_agents_section_persistence(test_config_path):
    assert save_recent_agent("coder", config_path=test_config_path)
    assert load_recent_agent(config_path=test_config_path) == "coder"

    assert save_default_agent("agent", config_path=test_config_path)
    assert load_default_agent(config_path=test_config_path) == "agent"

    assert clear_default_agent(config_path=test_config_path)
    assert load_default_agent(config_path=test_config_path) == "coder" # Fallback to recent


def test_theme_and_cross_table_preservation(test_config_path):
    # Write models, effort, agents, and theme
    save_recent_model("openai:gpt-4o", config_path=test_config_path)
    save_effort_for_model("openai:gpt-4o", "high", config_path=test_config_path)
    save_recent_agent("coder", config_path=test_config_path)
    save_theme_preference("tokyo-night", config_path=test_config_path)

    assert load_theme_preference(config_path=test_config_path) == "tokyo-night"

    # Read TOML to verify no tables were wiped
    with test_config_path.open("rb") as f:
        data = tomllib.load(f)

    assert data["models"]["recent"] == "openai:gpt-4o"
    assert data["effort"]["by_model"]["openai:gpt-4o"] == "high"
    assert data["agents"]["recent"] == "coder"
    assert data["ui"]["theme"] == "tokyo-night"


@pytest.mark.asyncio
async def test_model_and_effort_command_handlers(tmp_path, monkeypatch):
    test_config = tmp_path / "config.toml"
    monkeypatch.setattr("opscode.config.toml_config.CONFIG_PATH", test_config)

    handler = ModelHandler()
    ctx = CommandContext(app=None, raw_command="/model --default google_genai:gemini-3.6-flash", args="--default google_genai:gemini-3.6-flash")
    res = await handler.execute(ctx)
    assert res.success
    assert test_config.exists()

    with test_config.open("rb") as f:
        data = tomllib.load(f)
    assert data["models"]["default"] == "google_genai:gemini-3.6-flash"

    # Test /effort command persistence
    effort_handler = EffortHandler()
    ctx_eff = CommandContext(app=None, raw_command="/effort high", args="high", model_spec="google_genai:gemini-3.6-flash")
    res_eff = await effort_handler.execute(ctx_eff)
    assert res_eff.success

    with test_config.open("rb") as f:
        data2 = tomllib.load(f)
    assert data2["effort"]["by_model"]["google_genai:gemini-3.6-flash"] == "high"

    # Test /effort clear
    ctx_clear = CommandContext(app=None, raw_command="/effort clear", args="clear", model_spec="google_genai:gemini-3.6-flash")
    res_clear = await effort_handler.execute(ctx_clear)
    assert res_clear.success

    with test_config.open("rb") as f:
        data3 = tomllib.load(f)
    assert "google_genai:gemini-3.6-flash" not in data3.get("effort", {}).get("by_model", {})


