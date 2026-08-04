"""Unit tests for prompt builder — system prompt assembly and template rendering."""

import re
from pathlib import Path

import pytest

from dcoder.prompts import (
    MODEL_IDENTITY_RE,
    build_model_identity_section,
    get_base_system_prompt,
)


class TestBuildModelIdentitySection:
    """Tests for build_model_identity_section."""

    def test_returns_empty_for_no_name(self):
        assert build_model_identity_section(None) == ""
        assert build_model_identity_section("") == ""

    def test_basic_name_only(self):
        result = build_model_identity_section("claude-opus-4-6")
        assert "### Model Identity" in result
        assert "`claude-opus-4-6`" in result

    def test_with_provider(self):
        result = build_model_identity_section("claude-opus-4-6", provider="anthropic")
        assert "provider: anthropic" in result

    def test_with_context_limit(self):
        result = build_model_identity_section("gpt-5.1", context_limit=200000)
        assert "200,000 tokens" in result

    def test_with_unsupported_modalities_single(self):
        result = build_model_identity_section(
            "gemini-flash", unsupported_modalities=frozenset({"audio"})
        )
        assert "Audio" in result
        assert "not be available" in result

    def test_with_unsupported_modalities_multiple(self):
        result = build_model_identity_section(
            "model-x", unsupported_modalities=frozenset({"audio", "video"})
        )
        assert "audio and video" in result.lower() or "video and audio" in result.lower()

    def test_with_three_unsupported_modalities(self):
        result = build_model_identity_section(
            "model-x", unsupported_modalities=frozenset({"audio", "video", "image"})
        )
        assert "and" in result


class TestGetBaseSystemPrompt:
    """Tests for get_base_system_prompt."""

    def test_returns_nonempty_string(self):
        prompt = get_base_system_prompt()
        assert isinstance(prompt, str)
        # Only assert non-empty if template exists
        template = Path(__file__).parent.parent.parent.parent / "src" / "dcoder" / "prompts" / "templates" / "system_prompt.md"
        if template.exists():
            assert len(prompt) > 100

    def test_interactive_mode_differences(self):
        """Interactive and non-interactive modes should produce different prompts."""
        template = Path(__file__).parent.parent.parent.parent / "src" / "dcoder" / "prompts" / "templates" / "system_prompt.md"
        if not template.exists():
            pytest.skip("System prompt template not found")

        interactive_prompt = get_base_system_prompt(interactive=True)
        headless_prompt = get_base_system_prompt(interactive=False)
        assert interactive_prompt != headless_prompt
        assert "interactive" in interactive_prompt.lower() or "asks questions" in interactive_prompt.lower() or "ambiguous" in interactive_prompt.lower()
        assert "headless" in headless_prompt.lower() or "non-interactive" in headless_prompt.lower() or "autonomous" in headless_prompt.lower()

    def test_model_identity_injected(self):
        template = Path(__file__).parent.parent.parent.parent / "src" / "dcoder" / "prompts" / "templates" / "system_prompt.md"
        if not template.exists():
            pytest.skip("System prompt template not found")

        prompt = get_base_system_prompt(
            model_name="claude-opus-4-6",
            model_provider="anthropic",
            model_context_limit=200000,
        )
        assert "claude-opus-4-6" in prompt
        assert "anthropic" in prompt

    def test_working_directory_injected(self):
        template = Path(__file__).parent.parent.parent.parent / "src" / "dcoder" / "prompts" / "templates" / "system_prompt.md"
        if not template.exists():
            pytest.skip("System prompt template not found")

        prompt = get_base_system_prompt(cwd="/tmp/test-project")
        assert "/tmp/test-project" in prompt

    def test_restricted_fs_tools(self):
        template = Path(__file__).parent.parent.parent.parent / "src" / "dcoder" / "prompts" / "templates" / "system_prompt.md"
        if not template.exists():
            pytest.skip("System prompt template not found")

        prompt = get_base_system_prompt(fs_tools=["read_file", "list_dir"])
        assert "restricted" in prompt.lower()
        assert "`read_file`" in prompt

    def test_no_unreplaced_placeholders(self):
        """Final prompt should not contain any unreplaced {placeholder} markers."""
        template = Path(__file__).parent.parent.parent.parent / "src" / "dcoder" / "prompts" / "templates" / "system_prompt.md"
        if not template.exists():
            pytest.skip("System prompt template not found")

        prompt = get_base_system_prompt(
            model_name="test-model",
            model_provider="test",
            cwd="/tmp/test",
        )
        unreplaced = re.findall(r"\{[a-z_]+\}", prompt)
        assert unreplaced == [], f"Unreplaced placeholders found: {unreplaced}"


class TestModelIdentityRegex:
    """Tests for MODEL_IDENTITY_RE regex pattern."""

    def test_matches_model_identity_block(self):
        text = (
            "### Model Identity\n\n"
            "You are running as model `claude-opus`.\n\n"
            "### Next Section\n"
        )
        match = MODEL_IDENTITY_RE.search(text)
        assert match is not None
        assert "claude-opus" in match.group()
        assert "Next Section" not in match.group()

    def test_no_match_when_absent(self):
        text = "### Some Other Section\n\nContent here.\n"
        assert MODEL_IDENTITY_RE.search(text) is None
