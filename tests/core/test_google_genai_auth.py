"""Tests for Google GenAI / Vertex AI authentication and TUI model context propagation."""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from dcoder.model.factory import create_model
from dcoder.model.config import apply_stored_credentials
from dcoder.ui.textual_adapter import TextualAdapter


def test_apply_stored_credentials_google_genai(monkeypatch, tmp_path):
    """Test apply_stored_credentials exports GOOGLE_GENAI_USE_VERTEXAI to os.environ."""
    monkeypatch.setattr("dcoder.config.settings._load_dotenv", lambda **k: None)
    monkeypatch.setenv("GOOGLE_API_KEY", "test_key_123")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")

    applied = apply_stored_credentials("google_genai")
    assert applied is True
    assert os.environ.get("GOOGLE_API_KEY") == "test_key_123"
    assert os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") == "true"


def test_create_model_google_genai_vertexai(monkeypatch):
    """Test create_model for google_genai passes vertexai=True to model instance."""
    monkeypatch.setenv("GOOGLE_API_KEY", "mock_test_key_vertexai")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")

    res = create_model("google_genai:gemini-3.5-flash-lite")
    assert res.provider == "google_genai"
    assert res.model_name == "gemini-3.5-flash-lite"
    assert getattr(res.model, "vertexai", False) is True


@pytest.mark.asyncio
async def test_textual_adapter_stream_turn_passes_context():
    """Test TextualAdapter.stream_turn passes context with model to client.astream."""
    mock_client = MagicMock()
    
    async def fake_astream(*args, **kwargs):
        if False:
            yield None

    mock_client.astream = MagicMock(side_effect=fake_astream)

    adapter = TextualAdapter(client=mock_client, assistant_id="dcoder")

    context = {"model": "google_genai:gemini-3.5-flash-lite"}
    await adapter.stream_turn("Hello", thread_id="t1", context=context)

    mock_client.astream.assert_called_once()
    _, kwargs = mock_client.astream.call_args
    assert kwargs.get("context") == context


def test_extract_text_block_content():
    """Test _extract_text handles string content, list of dicts, and mixed blocks."""
    from dcoder.ui.textual_adapter import _extract_text

    assert _extract_text("Plain string") == "Plain string"
    assert _extract_text([{"type": "text", "text": "Hello world"}]) == "Hello world"
    assert _extract_text(["Hello ", {"text": "world"}]) == "Hello world"
    assert _extract_text(None) == ""
