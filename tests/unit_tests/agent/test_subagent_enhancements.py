import pytest
from unittest.mock import patch, MagicMock

from opscode.agent.factory import _subagent_cli_middleware, create_opscode_agent
from opscode.middleware.auto_mode import AutoModeHITLMiddleware, AsyncApprovalHITLMiddleware
from langchain.agents.middleware.human_in_the_loop import HumanInTheLoopMiddleware
from deepagents.middleware import FilesystemMiddleware


def test_subagent_cli_middleware_injects_hitl():
    # When interrupt_on is None, it should not inject HITL middleware
    middlewares_without_hitl = _subagent_cli_middleware(
        has_explicit_model=False,
        assistant_id="test",
        subagent_name="test_sub",
        interrupt_on=None,
    )
    assert not any(isinstance(mw, HumanInTheLoopMiddleware) for mw in middlewares_without_hitl)

    # When interrupt_on is provided, it should inject HITL middleware
    interrupt_on_config = {"write_file": {}}
    middlewares_with_hitl = _subagent_cli_middleware(
        has_explicit_model=False,
        assistant_id="test",
        subagent_name="test_sub",
        interrupt_on=interrupt_on_config,
    )
    assert any(isinstance(mw, HumanInTheLoopMiddleware) for mw in middlewares_with_hitl)


def test_subagent_cli_middleware_ordering():
    """Verify that AsyncApprovalHITLMiddleware is at index 0 when interrupt_on is provided."""
    interrupt_on_config = {"write_file": {}}
    middlewares = _subagent_cli_middleware(
        has_explicit_model=False,
        assistant_id="test",
        subagent_name="test_sub",
        interrupt_on=interrupt_on_config,
    )
    assert len(middlewares) > 0
    assert isinstance(middlewares[0], AsyncApprovalHITLMiddleware)



@patch("deepagents.create_deep_agent")
@patch("opscode.subagents.get_built_in_subagents")
@patch("opscode.subagents.list_subagents")
def test_create_opscode_agent_injects_filesystem_middleware(mock_list_subagents, mock_get_built_in, mock_create_deep_agent):
    # Mock built-in subagents to return a dummy subagent
    mock_list_subagents.return_value = []
    mock_get_built_in.return_value = [{"name": "dummy_subagent", "description": "dummy"}]
    
    # We just need it to return something valid, and capture the arguments passed to create_deep_agent
    mock_create_deep_agent.return_value = MagicMock()
    
    from langchain_core.language_models import BaseChatModel
    fake_model = MagicMock(spec=BaseChatModel)

    # Call create_opscode_agent with fs_tools
    create_opscode_agent(
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


@patch("deepagents.create_deep_agent")
@patch("opscode.subagents.get_built_in_subagents")
@patch("opscode.subagents.list_subagents")
def test_create_opscode_agent_sets_empty_subagent_interrupt_on(mock_list_subagents, mock_get_built_in, mock_create_deep_agent):
    mock_list_subagents.return_value = []
    mock_get_built_in.return_value = [{"name": "dummy_subagent", "description": "dummy"}]
    mock_create_deep_agent.return_value = MagicMock()

    from langchain_core.language_models import BaseChatModel
    fake_model = MagicMock(spec=BaseChatModel)

    create_opscode_agent(
        model=fake_model,
        interactive=True,
        auto_approve=False,
    )

    call_kwargs = mock_create_deep_agent.call_args.kwargs
    subagents = call_kwargs.get("subagents")
    assert subagents is not None

    dummy = next(sub for sub in subagents if sub["name"] == "dummy_subagent")
    assert dummy.get("interrupt_on") == {}


@patch("deepagents.create_deep_agent")
@patch("opscode.subagents.get_built_in_subagents")
@patch("opscode.subagents.list_subagents")
def test_create_opscode_agent_blocks_runnable_compiled_subagent_with_fs_tools(
    mock_list_subagents, mock_get_built_in, mock_create_deep_agent
):
    mock_list_subagents.return_value = []
    mock_get_built_in.return_value = [{"name": "compiled_sub", "runnable": MagicMock()}]

    from langchain_core.language_models import BaseChatModel

    fake_model = MagicMock(spec=BaseChatModel)

    with pytest.raises(ValueError, match="Cannot enforce --allow-fs-tools on compiled subagent"):
        create_opscode_agent(
            model=fake_model,
            fs_tools=["read_file"],
            interactive=False,
        )


@patch("opscode.subagents.loader.load_async_subagents")
@patch("deepagents.create_deep_agent")
@patch("opscode.subagents.get_built_in_subagents")
@patch("opscode.subagents.list_subagents")
def test_create_opscode_agent_loads_async_subagents_by_default(
    mock_list_subagents, mock_get_built_in, mock_create_deep_agent, mock_load_async
):
    mock_list_subagents.return_value = []
    mock_get_built_in.return_value = []
    mock_load_async.return_value = [
        {"name": "async_researcher", "description": "remote", "graph_id": "agent"}
    ]
    mock_create_deep_agent.return_value = MagicMock()

    from langchain_core.language_models import BaseChatModel

    fake_model = MagicMock(spec=BaseChatModel)

    create_opscode_agent(
        model=fake_model,
        interactive=False,
    )

    assert mock_load_async.called
    call_kwargs = mock_create_deep_agent.call_args.kwargs
    subagents = call_kwargs.get("subagents")
    assert subagents is not None
    assert any(sub.get("name") == "async_researcher" for sub in subagents)


@patch("deepagents.create_deep_agent")
@patch("opscode.subagents.get_built_in_subagents")
@patch("opscode.subagents.list_subagents")
def test_create_opscode_agent_sets_empty_subagent_interrupt_on_auto_approve(
    mock_list_subagents, mock_get_built_in, mock_create_deep_agent
):
    """Verify that auto_approve=True still sets explicit interrupt_on={} opt-out on subagents."""
    mock_list_subagents.return_value = []
    mock_get_built_in.return_value = [{"name": "dummy_subagent", "description": "dummy"}]
    mock_create_deep_agent.return_value = MagicMock()

    from langchain_core.language_models import BaseChatModel
    fake_model = MagicMock(spec=BaseChatModel)

    create_opscode_agent(
        model=fake_model,
        interactive=True,
        auto_approve=True,
    )

    call_kwargs = mock_create_deep_agent.call_args.kwargs
    subagents = call_kwargs.get("subagents")
    assert subagents is not None

    dummy = next(sub for sub in subagents if sub["name"] == "dummy_subagent")
    assert dummy.get("interrupt_on") == {}

    gp = next(sub for sub in subagents if sub["name"] == "general-purpose")
    assert gp.get("interrupt_on") == {}


def test_async_hitl_middleware_class_name():
    """Verify AsyncApprovalHITLMiddleware and AutoModeHITLMiddleware expose class attribute name."""
    from opscode.middleware.auto_mode_hitl import AsyncApprovalHITLMiddleware, AutoModeHITLMiddleware

    assert AsyncApprovalHITLMiddleware.name == "HumanInTheLoopMiddleware"
    assert AutoModeHITLMiddleware.name == "HumanInTheLoopMiddleware"


