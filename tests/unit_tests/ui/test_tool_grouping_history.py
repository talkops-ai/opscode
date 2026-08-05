"""Unit tests for tool grouping exclusions and thread history restoration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dcoder.ui.messages import (
    _TOOL_GROUP_EXCLUSIONS,
    MessageList,
    ToolCallMessage,
    ToolGroupSummary,
)


def test_tool_group_exclusions_contains_file_edits():
    """Verify that file edit and interactive tools are in _TOOL_GROUP_EXCLUSIONS."""
    assert "ask_user" in _TOOL_GROUP_EXCLUSIONS
    assert "edit_file" in _TOOL_GROUP_EXCLUSIONS
    assert "write_to_file" in _TOOL_GROUP_EXCLUSIONS
    assert "replace_file_content" in _TOOL_GROUP_EXCLUSIONS
    assert "write_todos" in _TOOL_GROUP_EXCLUSIONS


@pytest.mark.asyncio
async def test_message_list_clear_resets_active_tool_group():
    """Verify that clearing MessageList resets the active live tool group."""
    msg_list = MessageList()
    msg_list.remove_children = MagicMock()
    msg_list._active_tool_group = MagicMock()
    msg_list.clear()

    assert msg_list._active_tool_group is None
    assert len(msg_list._tool_calls) == 0


@pytest.mark.asyncio
async def test_add_tool_call_excludes_file_edits_from_live_group():
    """Verify that file edit tools are mounted as standalone widgets, not added to active live tool group."""
    msg_list = MessageList()
    msg_list.mount = MagicMock()

    # Standard tool should create a live group
    msg_list.add_tool_call(name="get_goal", call_id="c1", args={})
    assert msg_list._active_tool_group is not None

    # Excluded tool should NOT create or join active group
    msg_list._active_tool_group = None
    msg_list.add_tool_call(name="write_to_file", call_id="c2", args={"path": "variables.tf"})
    assert msg_list._active_tool_group is None


@pytest.mark.asyncio
async def test_load_thread_history_restores_goal_objective():
    """Verify that _load_thread_history restores active goal state using _restore_goal_rubric_state."""
    from langchain_core.messages import HumanMessage, AIMessage
    from dcoder.ui.app import DCoderApp

    app = DCoderApp()
    app._get_thread_state_values = AsyncMock(return_value={
        "_goal_objective": "i want to write vpc terraform module",
        "_goal_status": "active",
        "_goal_rubric": "Create VPC module",
        "messages": [
            HumanMessage(content="[SYSTEM] Goal set by the user."),
            AIMessage(content="", tool_calls=[{"id": "tc1", "name": "get_goal", "args": {}}]),
        ]
    })
    messages_container = MagicMock()
    messages_container.children = []
    app.query_one = MagicMock(return_value=messages_container)
    app._mount_message = AsyncMock()
    app._regroup_completed_tools = AsyncMock()

    await app._load_thread_history("test-thread-id")

    assert app._active_goal == "i want to write vpc terraform module"
    assert app._goal_status == "active"
    assert app._active_rubric == "Create VPC module"
    assert app._mount_message.called
    mounted_msg = app._mount_message.call_args[0][0]
    assert "/goal i want to write vpc terraform module" in getattr(mounted_msg, "_raw_content", "")


@pytest.mark.asyncio
async def test_load_thread_history_full_turn_with_assistant_response():
    """Verify that _load_thread_history mounts AssistantMessage text for full goal turns."""
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from dcoder.ui.app import DCoderApp
    from dcoder.ui.messages import AssistantMessage

    app = DCoderApp()
    app._get_thread_state_values = AsyncMock(return_value={
        "_goal_objective": "i want to write aws s3 module",
        "_goal_status": "active",
        "messages": [
            HumanMessage(content="[SYSTEM] Goal set by the user."),
            AIMessage(content="", tool_calls=[{"id": "tc1", "name": "get_goal", "args": {}}]),
            ToolMessage(tool_call_id="tc1", name="get_goal", content='{"objective": "i want to write aws s3 module"}'),
            AIMessage(content="The AWS S3 module has been created successfully."),
        ]
    })
    messages_container = MagicMock()
    messages_container.children = []
    app.query_one = MagicMock(return_value=messages_container)
    mounted_widgets = []
    app._mount_message = AsyncMock(side_effect=lambda w: mounted_widgets.append(w))
    app._regroup_completed_tools = AsyncMock()

    await app._load_thread_history("test-full-thread-id")

    # Assert AssistantMessage text was mounted
    assistant_msgs = [w for w in mounted_widgets if isinstance(w, AssistantMessage)]
    assert len(assistant_msgs) == 1
    assert "The AWS S3 module has been created successfully" in assistant_msgs[0]._content
