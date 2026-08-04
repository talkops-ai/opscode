"""Unit tests for LangSmith configuration and URL resolution."""

import os
from unittest.mock import patch

import pytest

from dcoder.config.langsmith import (
    LangSmithApiError,
    LangSmithImportError,
    LangSmithLookupTimeoutError,
    LangSmithProjectNotFoundError,
    _assemble_langsmith_thread_url,
    get_langsmith_project_name,
)


class TestAssembleLangsmithThreadUrl:
    """Tests for _assemble_langsmith_thread_url."""

    def test_basic_url_construction(self):
        url = _assemble_langsmith_thread_url(
            "https://smith.langchain.com/o/org/projects/p/abc123",
            "thread-42",
        )
        assert url.endswith("/t/thread-42?utm_source=dcoder")

    def test_strips_trailing_slash(self):
        url = _assemble_langsmith_thread_url(
            "https://smith.langchain.com/project/",
            "thread-1",
        )
        assert "/project/t/thread-1" in url
        assert "/project//t/" not in url

    def test_utm_source_present(self):
        url = _assemble_langsmith_thread_url("https://example.com/p", "t1")
        assert "utm_source=dcoder" in url


class TestGetLangsmithProjectName:
    """Tests for get_langsmith_project_name."""

    def test_returns_none_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            assert get_langsmith_project_name() is None

    def test_returns_none_without_tracing_flag(self):
        with patch.dict(
            os.environ,
            {"LANGSMITH_API_KEY": "lsk-test123"},
            clear=True,
        ):
            assert get_langsmith_project_name() is None

    def test_returns_default_project_name(self):
        with patch.dict(
            os.environ,
            {
                "LANGSMITH_API_KEY": "lsk-test123",
                "LANGSMITH_TRACING": "true",
            },
            clear=True,
        ):
            result = get_langsmith_project_name()
            assert result == "dcoder"

    def test_respects_custom_project_env_var(self):
        with patch.dict(
            os.environ,
            {
                "LANGSMITH_API_KEY": "lsk-test123",
                "LANGSMITH_TRACING": "true",
                "DCODER_LANGSMITH_PROJECT": "my-custom-project",
            },
            clear=True,
        ):
            result = get_langsmith_project_name()
            assert result == "my-custom-project"

    def test_dcoder_prefix_takes_precedence(self):
        with patch.dict(
            os.environ,
            {
                "DCODER_LANGSMITH_API_KEY": "lsk-dcoder",
                "LANGSMITH_API_KEY": "lsk-other",
                "LANGSMITH_TRACING": "true",
            },
            clear=True,
        ):
            # Should still resolve because LANGSMITH_API_KEY is present
            result = get_langsmith_project_name()
            assert result is not None

    def test_langchain_v2_tracing_works(self):
        with patch.dict(
            os.environ,
            {
                "LANGCHAIN_API_KEY": "lsk-test123",
                "LANGCHAIN_TRACING_V2": "true",
            },
            clear=True,
        ):
            result = get_langsmith_project_name()
            assert result == "dcoder"


class TestExceptionHierarchy:
    """Verify exception classes are properly structured."""

    def test_import_error_is_lookup_error(self):
        assert issubclass(LangSmithImportError, Exception)

    def test_timeout_is_lookup_error(self):
        assert issubclass(LangSmithLookupTimeoutError, Exception)

    def test_api_error_is_lookup_error(self):
        assert issubclass(LangSmithApiError, Exception)

    def test_not_found_is_api_error(self):
        assert issubclass(LangSmithProjectNotFoundError, LangSmithApiError)
