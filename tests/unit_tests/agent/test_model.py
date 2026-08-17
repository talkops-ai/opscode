from unittest.mock import patch, MagicMock
import pytest

from opscode.exceptions import MissingCredentialsError
from opscode.model.factory import detect_provider, create_model

def test_detect_provider():
    assert detect_provider("claude-3-5-sonnet") == "anthropic"
    assert detect_provider("gpt-4o") == "openai"
    assert detect_provider("gemini-1.5-pro") == "google_genai"
    assert detect_provider("unknown-model-name") is None


@patch("opscode.model.factory.has_provider_credentials")
@patch("opscode.model.factory._create_model_via_init")
def test_create_model(mock_init, mock_has_creds):
    mock_has_creds.return_value = True
    mock_model = MagicMock()
    mock_model.profile = {"max_input_tokens": 100000}
    mock_init.return_value = mock_model

    result = create_model("openai:gpt-4o")
    assert result.model == mock_model
    assert result.model_name == "gpt-4o"
    assert result.provider == "openai"
    assert result.context_limit == 100000


@patch("opscode.model.factory.has_provider_credentials")
def test_create_model_missing_credentials(mock_has_creds):
    mock_has_creds.return_value = False
    
    with pytest.raises(MissingCredentialsError):
        create_model("openai:gpt-4o")
