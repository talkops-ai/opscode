"""Unit tests for generic AuthPromptScreen and AuthManagerScreen LangSmith integration."""

import os
from unittest.mock import MagicMock, patch
import pytest

from opscode.ui.widgets.auth import AuthPromptScreen, AuthResult, PROVIDER_DISPLAY_NAMES, PROVIDER_API_KEY_URLS, is_langsmith
from opscode.ui.widgets.auth_manager import AuthManagerScreen, _KNOWN_PROVIDERS


def test_langsmith_provider_metadata():
    assert is_langsmith("langsmith") is True
    assert is_langsmith("LangSmith") is True
    assert is_langsmith("tracing") is True
    assert "langsmith" in PROVIDER_DISPLAY_NAMES
    assert PROVIDER_DISPLAY_NAMES["langsmith"] == "LangSmith (tracing)"
    assert "langsmith" in PROVIDER_API_KEY_URLS
    assert "smith.langchain.com" in PROVIDER_API_KEY_URLS["langsmith"]
    assert "langsmith" in _KNOWN_PROVIDERS


def test_langsmith_auth_prompt_screen_init():
    screen = AuthPromptScreen("langsmith")
    assert screen._is_langsmith is True
    assert screen._advanced_visible is False


@patch("os.makedirs")
@patch("builtins.open")
def test_langsmith_auth_perform_save(mock_open, mock_makedirs):
    screen = AuthPromptScreen("langsmith")
    mock_app = MagicMock()
    screen._app = mock_app  # type: ignore[attr-defined]

    mock_key_input = MagicMock()
    mock_key_input.value = "ls_test_api_key_12345"

    mock_proj_input = MagicMock()
    mock_proj_input.value = "my-test-proj"

    mock_ep_input = MagicMock()
    mock_ep_input.value = "https://eu.api.smith.langchain.com"

    mock_radio_eu = MagicMock()
    mock_radio_eu.value = True

    def query_side_effect(selector: str, *args, **kwargs):
        if selector == "#auth-prompt-input":
            return mock_key_input
        if selector == "#auth-prompt-project-input":
            return mock_proj_input
        if selector == "#auth-prompt-base-url":
            return mock_ep_input
        if selector == "#reg-eu":
            return mock_radio_eu
        return MagicMock()

    screen.query_one = MagicMock(side_effect=query_side_effect)
    screen.dismiss = MagicMock()

    screen._perform_save()

    assert os.environ.get("LANGSMITH_API_KEY") == "ls_test_api_key_12345"
    assert os.environ.get("LANGSMITH_TRACING") == "true"
    assert os.environ.get("LANGSMITH_PROJECT") == "my-test-proj"
    assert os.environ.get("LANGSMITH_ENDPOINT") == "https://eu.api.smith.langchain.com"
    screen.dismiss.assert_called_once_with(AuthResult.SAVED)
