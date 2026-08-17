"""Shared fixtures for integration tests.

Integration tests hit real LLM APIs and external services.
These fixtures handle model creation, cost caps, and auto-skipping
when required API keys are missing.
"""

from __future__ import annotations

import os

import pytest


# ── Auto-skip when API keys are missing ─────────────────────────────

def _has_any_api_key() -> bool:
    """Check if at least one LLM provider API key is configured."""
    key_vars = [
        "GOOGLE_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "OPSCODE_GOOGLE_API_KEY",
        "OPSCODE_ANTHROPIC_API_KEY",
        "OPSCODE_OPENAI_API_KEY",
    ]
    return any(os.environ.get(k) for k in key_vars)


@pytest.fixture(autouse=True)
def skip_if_no_api_key():
    """Auto-skip integration tests when no LLM API key is available."""
    if not _has_any_api_key():
        pytest.skip("No LLM API key configured — skipping integration test")


# ── Test model (cheap/fast variant) ─────────────────────────────────

INTEGRATION_TEST_MODEL = os.environ.get(
    "OPSCODE_TEST_MODEL", "google-genai:gemini-2.0-flash"
)


@pytest.fixture
def test_model_spec() -> str:
    """Return the model spec string for integration tests."""
    return INTEGRATION_TEST_MODEL
