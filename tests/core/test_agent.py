from unittest.mock import patch, MagicMock
from langchain_core.language_models import BaseChatModel
from dcoder.agent.factory import create_dcoder_agent, CLIContextSchema

def test_cli_context_schema():
    ctx = CLIContextSchema(model="anthropic:claude-3", auto_approve=True)
    assert ctx.model == "anthropic:claude-3"
    assert ctx.auto_approve is True


@patch("deepagents.create_deep_agent")
def test_create_dcoder_agent(mock_create_deep_agent):
    mock_model = MagicMock(spec=BaseChatModel)
    mock_agent = MagicMock()
    mock_create_deep_agent.return_value = mock_agent

    agent, backend = create_dcoder_agent(
        model=mock_model,
        assistant_id="test-agent",
        enable_shell=True,
        auto_approve=True,
    )

    assert agent == mock_agent
    mock_create_deep_agent.assert_called_once()
    kwargs = mock_create_deep_agent.call_args.kwargs
    assert kwargs["model"] == mock_model
    assert kwargs["name"] == "test-agent"
    assert kwargs["interrupt_on"] == {}
    
    # Verify subagents compilation and middleware injection (C1)
    subagents = kwargs["subagents"]
    assert subagents is not None
    assert len(subagents) > 0
    for s in subagents:
        assert "middleware" in s
        assert len(s["middleware"]) > 0
