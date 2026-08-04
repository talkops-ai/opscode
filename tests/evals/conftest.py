"""Shared fixtures for eval tests.

Eval tests assess agent trajectory and outcome quality using
LangSmith datasets and AgentEvals evaluators.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


EVALS_DIR = Path(__file__).parent
DATASETS_DIR = EVALS_DIR / "datasets"


@pytest.fixture
def datasets_dir() -> Path:
    """Return the path to the eval datasets directory."""
    return DATASETS_DIR


@pytest.fixture
def require_langsmith():
    """Skip test if LangSmith is not configured. Use explicitly on tests that need LLM."""
    api_key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    tracing = os.environ.get("LANGSMITH_TRACING") or os.environ.get("LANGCHAIN_TRACING_V2")
    if not (api_key and tracing):
        pytest.skip("LangSmith not configured — skipping eval test")
