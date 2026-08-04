"""Unit tests for TraceHandler (/trace) and LangSmith helper functions."""

from unittest.mock import MagicMock, patch
import pytest

from dcoder.commands._base import CommandContext
from dcoder.commands.power.trace import TraceHandler
from dcoder.config.langsmith import (
    LangSmithApiError,
    LangSmithImportError,
    LangSmithLookupTimeoutError,
    LangSmithProjectNotFoundError,
    _assemble_langsmith_thread_url,
    get_langsmith_project_name,
)


def test_assemble_langsmith_thread_url():
    proj_url = "https://smith.langchain.com/o/org123/projects/p/proj456"
    thread_id = "thread_abc123"
    url = _assemble_langsmith_thread_url(proj_url, thread_id)
    assert url == "https://smith.langchain.com/o/org123/projects/p/proj456/t/thread_abc123?utm_source=dcoder"


@patch("dcoder.config.langsmith.resolve_env_var")
def test_get_langsmith_project_name_unconfigured(mock_resolve):
    mock_resolve.return_value = None
    assert get_langsmith_project_name() is None


@patch("dcoder.config.langsmith.resolve_env_var")
def test_get_langsmith_project_name_configured(mock_resolve):
    def env_side_effect(name: str):
        if name in ("LANGSMITH_API_KEY", "LANGSMITH_TRACING"):
            return "true_or_key"
        if name == "LANGSMITH_PROJECT":
            return "my-custom-project"
        return None

    mock_resolve.side_effect = env_side_effect
    assert get_langsmith_project_name() == "my-custom-project"


@pytest.mark.asyncio
@patch("dcoder.commands.power.trace.get_langsmith_project_name")
async def test_trace_handler_not_configured(mock_get_proj):
    mock_get_proj.return_value = None
    ctx = CommandContext(app=None, settings=None)
    handler = TraceHandler()

    res = await handler.execute(ctx)
    assert res.success is False
    assert res.message is not None and "tracing is not configured" in res.message.lower()
    assert res.message is not None and "/auth" in res.message


@pytest.mark.asyncio
@patch("dcoder.commands.power.trace.webbrowser.open")
@patch("dcoder.commands.power.trace.fetch_langsmith_project_url_or_raise")
@patch("dcoder.commands.power.trace.get_langsmith_project_name")
async def test_trace_handler_success(mock_get_proj, mock_fetch_url, mock_open):
    mock_get_proj.return_value = "dcoder"
    mock_fetch_url.return_value = "https://smith.langchain.com/o/org/projects/p/dcoder"

    mock_app = MagicMock()
    mock_app._agent_thread_id = "thread-12345"

    ctx = CommandContext(app=mock_app, settings=None)
    handler = TraceHandler()

    res = await handler.execute(ctx)
    assert res.success is True
    assert res.message is not None and "https://smith.langchain.com/o/org/projects/p/dcoder/t/thread-12345?utm_source=dcoder" in res.message
    mock_open.assert_called_once()


@pytest.mark.asyncio
@patch("dcoder.commands.power.trace.fetch_langsmith_project_url_or_raise")
@patch("dcoder.commands.power.trace.get_langsmith_project_name")
async def test_trace_handler_project_not_found(mock_get_proj, mock_fetch_url):
    mock_get_proj.return_value = "dcoder"
    mock_fetch_url.side_effect = LangSmithProjectNotFoundError("404 Project Not Found")

    ctx = CommandContext(app=None, settings=None)
    handler = TraceHandler()

    res = await handler.execute(ctx)
    assert res.success is False
    assert res.message is not None and "No traces have been recorded" in res.message


@pytest.mark.asyncio
@patch("dcoder.commands.power.trace.fetch_langsmith_project_url_or_raise")
@patch("dcoder.commands.power.trace.get_langsmith_project_name")
async def test_trace_handler_import_error(mock_get_proj, mock_fetch_url):
    mock_get_proj.return_value = "dcoder"
    mock_fetch_url.side_effect = LangSmithImportError("langsmith not installed")

    ctx = CommandContext(app=None, settings=None)
    handler = TraceHandler()

    res = await handler.execute(ctx)
    assert res.success is False
    assert res.message is not None and "package is not installed" in res.message
