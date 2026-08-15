"""Tests for modular theme registry, persistence, and ThemeSelectorScreen modal."""

import os
from unittest.mock import patch
from pathlib import Path

from dcoder.ui.theme import (
    get_registry,
    load_theme_preference,
    save_theme_preference,
    save_terminal_theme_mapping,
    reload_registry,
)
from dcoder.ui.widgets.theme_selector import ThemeSelectorScreen


def test_theme_registry_contains_dcoder_and_textual_builtins():
    reload_registry()
    registry = get_registry()

    assert "dcoder-dark" in registry
    assert "dcoder-light" in registry
    assert "langchain" in registry
    assert "langchain-light" in registry
    assert registry["dcoder-dark"].label == "DevOps Dark"
    assert registry["dcoder-light"].label == "DevOps Light"
    assert registry["langchain"].label == "LangChain Dark"
    assert registry["langchain-light"].label == "LangChain Light"

    # Verify Textual built-in themes are present
    assert "catppuccin-mocha" in registry or "dracula" in registry or "nord" in registry



def test_save_and_load_theme_preference(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    with patch("dcoder.ui.theme.CONFIG_PATH", config_file):
        assert save_theme_preference("nord")
        assert load_theme_preference() == "nord"


def test_save_and_load_terminal_theme_mapping(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    with patch("dcoder.ui.theme.CONFIG_PATH", config_file), \
         patch.dict(os.environ, {"TERM_PROGRAM": "iTerm.app"}):
        assert save_terminal_theme_mapping("iTerm.app", "catppuccin-mocha")
        assert load_theme_preference() == "catppuccin-mocha"


def test_theme_selector_screen_initialization():
    screen = ThemeSelectorScreen(current_theme="dcoder-dark")
    assert screen._current_theme == "dcoder-dark"
    formatted = screen._format_option("dcoder-dark", "DevOps Dark")
    assert "current" in formatted
