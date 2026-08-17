"""Root pytest configuration — markers, environment sandboxing, and path-based marker injection."""

from __future__ import annotations

import os

import pytest


# ── Environment sandboxing ──────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """Automatically clean critical environment variables before each test."""
    monkeypatch.delenv("OPSCODE_PROJECT_ROOT", raising=False)


# ── Auto-apply markers based on test path ───────────────────────────

def pytest_collection_modifyitems(config, items):
    """Automatically tag tests with markers based on their location."""
    for item in items:
        path_str = str(item.fspath)
        if "/unit_tests/" in path_str:
            item.add_marker(pytest.mark.unit)
        elif "/integration_tests/" in path_str:
            item.add_marker(pytest.mark.integration)
        elif "/evals/" in path_str:
            item.add_marker(pytest.mark.eval)
        else:
            # Legacy tests in tests/ or tests/core/ get the unit marker
            item.add_marker(pytest.mark.unit)
