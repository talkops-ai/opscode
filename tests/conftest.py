"""Shared pytest configuration and fixtures."""

import pytest

@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """Automatically clean critical environment variables before each test."""
    # Ensure tests run in a sandbox without leaking developer's local env
    monkeypatch.delenv("DCODER_PROJECT_ROOT", raising=False)
