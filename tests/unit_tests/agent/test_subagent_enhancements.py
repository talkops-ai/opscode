import pytest
from unittest.mock import patch, MagicMock

from dcoder.agent.factory import _subagent_cli_middleware, create_dcoder_agent
from dcoder.middleware.auto_mode import AutoModeHITLMiddleware
from deepagents.middleware import FilesystemMiddleware


def test_subagent_cli_middleware_injects_hitl():
    # When interrupt_on is None, it should not inject AutoModeHITLMiddleware
    middlewares_without_hitl = _subagent_cli_middleware(
        has_explicit_model=False,
        assistant_id="test",
        subagent_name="test_sub",
        interrupt_on=None,
    )
    assert not any(isinstance(mw, AutoModeHITLMiddleware) for mw in middlewares_without_hitl)

    # When interrupt_on is provided, it should inject AutoModeHITLMiddleware
    interrupt_on_config = {"write_file": {}}
    middlewares_with_hitl = _subagent_cli_middleware(
        has_explicit_model=False,
        assistant_id="test",
        subagent_name="test_sub",
        interrupt_on=interrupt_on_config,
    )
    assert any(isinstance(mw, AutoModeHITLMiddleware) for mw in middlewares_with_hitl)


@patch("deepagents.create_deep_agent")
@patch("dcoder.subagents.get_built_in_subagents")
@patch("dcoder.subagents.list_subagents")
def test_create_dcoder_agent_injects_filesystem_middleware(mock_list_subagents, mock_get_built_in, mock_create_deep_agent):
    # Mock built-in subagents to return a dummy subagent
    mock_list_subagents.return_value = []
    mock_get_built_in.return_value = [{"name": "dummy_subagent", "description": "dummy"}]
    
    # We just need it to return something valid, and capture the arguments passed to create_deep_agent
    mock_create_deep_agent.return_value = MagicMock()
    
    from langchain_core.language_models import BaseChatModel
    fake_model = MagicMock(spec=BaseChatModel)

    # Call create_dcoder_agent with fs_tools
    create_dcoder_agent(
        model=fake_model,
        fs_tools=["read_file", "write_file"],
        interactive=False,
        auto_approve=True,
    )
    
    # Verify create_deep_agent was called
    assert mock_create_deep_agent.called
    
    # Extract the subagents list passed to create_deep_agent
    call_kwargs = mock_create_deep_agent.call_args.kwargs
    subagents = call_kwargs.get("subagents")
    assert subagents is not None
    assert len(subagents) > 0
    
    # Find the dummy subagent in the compiled subagents
    dummy = next(sub for sub in subagents if sub["name"] == "dummy_subagent")
    
    # Verify FilesystemMiddleware is in the dummy's middleware stack
    dummy_middlewares = dummy.get("middleware", [])
    fs_middlewares = [mw for mw in dummy_middlewares if isinstance(mw, FilesystemMiddleware)]
    assert len(fs_middlewares) == 1
    
    # Verify the tools in FilesystemMiddleware match what was passed
    tool_names = [t.name for t in fs_middlewares[0].tools]
    assert tool_names == ["read_file", "write_file"]
