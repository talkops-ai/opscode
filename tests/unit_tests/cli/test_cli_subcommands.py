"""Comprehensive tests for CLI subcommands, options, and model auto-detection."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opscode.cli.main import cli_main, parse_args
from opscode.model.factory import detect_provider, normalize_model_spec


# ── Model Auto-detection & Normalization ────────────────────


class TestModelNormalization:
    """Test model prefix detection and spec normalization."""

    def test_detect_provider_prefixes(self):
        assert detect_provider("gpt-4o") == "openai"
        assert detect_provider("gpt-5.5") == "openai"
        assert detect_provider("o1-preview") == "openai"
        assert detect_provider("o3-mini") == "openai"
        assert detect_provider("o4-high") == "openai"
        assert detect_provider("claude-3-7-sonnet") == "anthropic"
        assert detect_provider("claude-opus-4-8") == "anthropic"
        assert detect_provider("gemini-2.5-pro") == "google_genai"
        assert detect_provider("deepseek-chat") == "deepseek"
        assert detect_provider("groq/llama-3") == "groq"
        assert detect_provider("mistral-large") == "mistralai"
        assert detect_provider("mixtral-8x7b") == "mistralai"
        assert detect_provider("command-r-plus") == "cohere"
        assert detect_provider("grok-2") == "xai"
        assert detect_provider("sonar-medium") == "perplexity"

    def test_normalize_model_spec(self):
        # Bare model names get provider prepended
        assert normalize_model_spec("gpt-5.5") == "openai:gpt-5.5"
        assert normalize_model_spec("claude-opus-4-8") == "anthropic:claude-opus-4-8"
        assert normalize_model_spec("gemini-2.5-flash") == "google_genai:gemini-2.5-flash"
        assert normalize_model_spec("deepseek-coder") == "deepseek:deepseek-coder"

        # Explicit provider:model specs stay untouched
        assert normalize_model_spec("anthropic:claude-opus-4-8") == "anthropic:claude-opus-4-8"
        assert normalize_model_spec("openai:gpt-5.5") == "openai:gpt-5.5"
        assert normalize_model_spec("bedrock:anthropic.claude-v2") == "bedrock:anthropic.claude-v2"

        # Unknown bare models stay as-is
        assert normalize_model_spec("custom-fine-tuned-model") == "custom-fine-tuned-model"


# ── Subcommand Dispatch Tests ───────────────────────────────


class TestSubcommandDispatch:
    """Test CLI subcommand parsers and handlers."""

    def test_auth_list_json(self, capsys):
        with patch.object(sys, "argv", ["opscode", "auth", "list", "--json"]):
            with pytest.raises(SystemExit) as exc:
                cli_main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "auth list"
        assert isinstance(data["data"], list)

    def test_auth_path(self, capsys):
        with patch.object(sys, "argv", ["opscode", "auth", "path", "--json"]):
            with pytest.raises(SystemExit) as exc:
                cli_main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "auth path"
        assert "path" in data["data"]

    def test_config_summary_json(self, capsys):
        with patch.object(sys, "argv", ["opscode", "config", "--json"]):
            with pytest.raises(SystemExit) as exc:
                cli_main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "config"
        assert isinstance(data["data"], list)

    def test_config_get_json(self, capsys):
        with patch.object(sys, "argv", ["opscode", "config", "get", "models.default", "--json"]):
            with pytest.raises(SystemExit) as exc:
                cli_main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "config get"

    def test_config_path_json(self, capsys):
        with patch.object(sys, "argv", ["opscode", "config", "path", "--json"]):
            with pytest.raises(SystemExit) as exc:
                cli_main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "config path"
        assert "config_toml" in data["data"]

    def test_mcp_config_json(self, capsys):
        with patch.object(sys, "argv", ["opscode", "mcp", "config", "--json"]):
            with pytest.raises(SystemExit) as exc:
                cli_main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "mcp config"
        assert "discovery_paths" in data["data"]

    def test_mcp_list_json(self, capsys):
        with patch.object(sys, "argv", ["opscode", "mcp", "list", "--json"]):
            with pytest.raises(SystemExit) as exc:
                cli_main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "mcp list"
        assert isinstance(data["data"], list)

    def test_skills_list_json(self, capsys):
        with patch.object(sys, "argv", ["opscode", "skills", "list", "--json"]):
            with pytest.raises(SystemExit) as exc:
                cli_main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "skills list"
        assert isinstance(data["data"], list)

    def test_agents_list_json(self, capsys):
        with patch.object(sys, "argv", ["opscode", "agents", "list", "--json"]):
            with pytest.raises(SystemExit) as exc:
                cli_main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "agents list"
        assert any(a["name"] == "agent" for a in data["data"])

    def test_tools_list_json(self, capsys):
        with patch.object(sys, "argv", ["opscode", "tools", "list", "--json"]):
            with pytest.raises(SystemExit) as exc:
                cli_main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "tools list"
        assert any(t["name"] == "execute" for t in data["data"])

    def test_tools_install_json(self, capsys):
        with patch.object(sys, "argv", ["opscode", "tools", "install", "--json"]):
            with pytest.raises(SystemExit) as exc:
                cli_main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "tools install"
        assert data["data"]["tool"] == "ripgrep"

    def test_doctor_json(self, capsys):
        with patch.object(sys, "argv", ["opscode", "doctor", "--json"]):
            with pytest.raises(SystemExit) as exc:
                cli_main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "doctor"
        assert "healthy" in data["data"]
        assert "sections" in data["data"]

    def test_threads_list_json(self, capsys):
        with patch.object(sys, "argv", ["opscode", "threads", "list", "--json"]):
            with patch("opscode.state.session.list_threads", new_callable=AsyncMock) as mock_list:
                mock_list.return_value = [
                    {
                        "thread_id": "t-123",
                        "agent_name": "opscode",
                        "message_count": 5,
                        "updated_at": "2026-08-14T00:00:00Z",
                        "created_at": "2026-08-14T00:00:00Z",
                    }
                ]
                with pytest.raises(SystemExit) as exc:
                    cli_main()
                assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "threads list"
        assert len(data["data"]) == 1
        assert data["data"][0]["thread_id"] == "t-123"


# ── Default Model Flag Tests ────────────────────────────────


class TestDefaultModelFlags:
    """Test --default-model and --clear-default-model flags."""

    def test_set_default_model(self, capsys):
        with patch("opscode.model.config.save_default_model", return_value=True) as mock_save:
            with patch.object(sys, "argv", ["opscode", "--default-model", "gpt-5.5"]):
                with pytest.raises(SystemExit) as exc:
                    cli_main()
                assert exc.value.code == 0
            mock_save.assert_called_once_with("openai:gpt-5.5")
        captured = capsys.readouterr()
        assert "Default model set to openai:gpt-5.5" in captured.out

    def test_show_default_model(self, capsys):
        with patch("opscode.model.config.load_default_model", return_value="anthropic:claude-opus-4-8"):
            with patch.object(sys, "argv", ["opscode", "--default-model"]):
                with pytest.raises(SystemExit) as exc:
                    cli_main()
                assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "Default model: anthropic:claude-opus-4-8" in captured.out

    def test_clear_default_model(self, capsys):
        with patch("opscode.model.config.clear_default_model", return_value=True) as mock_clear:
            with patch.object(sys, "argv", ["opscode", "--clear-default-model"]):
                with pytest.raises(SystemExit) as exc:
                    cli_main()
                assert exc.value.code == 0
            mock_clear.assert_called_once()
        captured = capsys.readouterr()
        assert "Default model cleared." in captured.out
