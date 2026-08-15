import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, Mock
from opscode.ui.textual_adapter import TextualAdapter
from langgraph.types import Command


@pytest.mark.asyncio
async def test_textual_adapter_interrupt_handling():
    """Verify that an __interrupt__ updates chunk triggers approval flow and resumes correctly."""
    loop = asyncio.get_running_loop()

    async def mock_request_approval(action_requests, assistant_id):
        fut = loop.create_future()
        fut.set_result({"type": "approve"})
        return fut

    adapter = TextualAdapter(
        app=MagicMock(),
        client=MagicMock(),
        assistant_id="mock_id",
        status_bar=MagicMock(),
        request_approval=mock_request_approval,
    )

    captured_resume = None

    async def mock_astream(stream_input, *args, **kwargs):
        nonlocal captured_resume
        if isinstance(stream_input, Command) and stream_input.resume:
            captured_resume = stream_input.resume
            return

        interrupt_obj = Mock()
        interrupt_obj.id = "int_123"
        interrupt_obj.value = {
            "action_requests": [{"name": "write_file", "args": {"file_path": "test.txt"}}],
            "review_configs": [],
        }
        yield ((), "updates", {"__interrupt__": [interrupt_obj]})

    adapter._client.astream = mock_astream

    await adapter.stream_turn(prompt="Test", thread_id="t1")

    assert captured_resume == {
        "int_123": {
            "decisions": [{"type": "approve"}]
        }
    }


@pytest.mark.asyncio
async def test_textual_adapter_interrupt_reject_with_message():
    """Verify that rejection with a custom reason message is included in decisions."""
    loop = asyncio.get_running_loop()

    async def mock_request_approval(action_requests, assistant_id):
        fut = loop.create_future()
        fut.set_result({"type": "reject", "message": "Do not delete production files"})
        return fut

    adapter = TextualAdapter(
        app=MagicMock(),
        client=MagicMock(),
        assistant_id="mock_id",
        status_bar=MagicMock(),
        request_approval=mock_request_approval,
    )

    captured_resume = None

    async def mock_astream(stream_input, *args, **kwargs):
        nonlocal captured_resume
        if isinstance(stream_input, Command) and stream_input.resume:
            captured_resume = stream_input.resume
            return

        interrupt_obj = Mock()
        interrupt_obj.id = "int_reject"
        interrupt_obj.value = {
            "action_requests": [{"name": "delete_file", "args": {"file_path": "prod.tf"}}],
            "review_configs": [],
        }
        yield ((), "updates", {"__interrupt__": [interrupt_obj]})

    adapter._client.astream = mock_astream

    await adapter.stream_turn(prompt="Test", thread_id="t1")

    assert captured_resume == {
        "int_reject": {
            "decisions": [{"type": "reject", "message": "Do not delete production files"}]
        }
    }


@pytest.mark.asyncio
async def test_textual_adapter_interrupt_auto_approve_all():
    """Verify that auto_approve_all notifies app._on_auto_approve_enabled and approves actions."""
    loop = asyncio.get_running_loop()
    mock_app = MagicMock()
    auto_approve_callback_called = False

    async def mock_on_auto_approve_enabled():
        nonlocal auto_approve_callback_called
        auto_approve_callback_called = True
        return True

    mock_app._on_auto_approve_enabled = mock_on_auto_approve_enabled

    async def mock_request_approval(action_requests, assistant_id):
        fut = loop.create_future()
        fut.set_result({"type": "auto_approve_all"})
        return fut

    adapter = TextualAdapter(
        app=mock_app,
        client=MagicMock(),
        assistant_id="mock_id",
        status_bar=MagicMock(),
        request_approval=mock_request_approval,
    )

    captured_resume = None

    async def mock_astream(stream_input, *args, **kwargs):
        nonlocal captured_resume
        if isinstance(stream_input, Command) and stream_input.resume:
            captured_resume = stream_input.resume
            return

        interrupt_obj = Mock()
        interrupt_obj.id = "int_auto"
        interrupt_obj.value = {
            "action_requests": [{"name": "run_command", "args": {"command": "echo hi"}}],
            "review_configs": [],
        }
        yield ((), "updates", {"__interrupt__": [interrupt_obj]})

    adapter._client.astream = mock_astream

    await adapter.stream_turn(prompt="Test", thread_id="t1")

    assert auto_approve_callback_called is True
    assert captured_resume == {
        "int_auto": {
            "decisions": [{"type": "approve"}]
        }
    }


@pytest.mark.asyncio
async def test_textual_adapter_interrupt_multiple_actions():
    """Verify multiple action requests in a single interrupt all get decision entries."""
    loop = asyncio.get_running_loop()

    async def mock_request_approval(action_requests, assistant_id):
        assert len(action_requests) == 2
        fut = loop.create_future()
        fut.set_result({"type": "approve"})
        return fut

    adapter = TextualAdapter(
        app=MagicMock(),
        client=MagicMock(),
        assistant_id="mock_id",
        status_bar=MagicMock(),
        request_approval=mock_request_approval,
    )

    captured_resume = None

    async def mock_astream(stream_input, *args, **kwargs):
        nonlocal captured_resume
        if isinstance(stream_input, Command) and stream_input.resume:
            captured_resume = stream_input.resume
            return

        interrupt_obj = Mock()
        interrupt_obj.id = "int_multi"
        interrupt_obj.value = {
            "action_requests": [
                {"name": "write_file", "args": {"file_path": "a.txt"}},
                {"name": "write_file", "args": {"file_path": "b.txt"}},
            ],
            "review_configs": [],
        }
        yield ((), "updates", {"__interrupt__": [interrupt_obj]})

    adapter._client.astream = mock_astream

    await adapter.stream_turn(prompt="Test", thread_id="t1")

    assert captured_resume == {
        "int_multi": {
            "decisions": [{"type": "approve"}, {"type": "approve"}]
        }
    }


@pytest.mark.asyncio
async def test_textual_adapter_interrupt_multiple_subagents():
    """Verify interrupts from multiple subagents in a single chunk are handled."""
    loop = asyncio.get_running_loop()
    approval_counts = 0

    async def mock_request_approval(action_requests, assistant_id):
        nonlocal approval_counts
        approval_counts += 1
        fut = loop.create_future()
        fut.set_result({"type": "approve"})
        return fut

    adapter = TextualAdapter(
        app=MagicMock(),
        client=MagicMock(),
        assistant_id="mock_id",
        status_bar=MagicMock(),
        request_approval=mock_request_approval,
    )

    captured_resume = None

    async def mock_astream(stream_input, *args, **kwargs):
        nonlocal captured_resume
        if isinstance(stream_input, Command) and stream_input.resume:
            captured_resume = stream_input.resume
            return

        int_obj1 = Mock()
        int_obj1.id = "int_subagent_1"
        int_obj1.value = {
            "action_requests": [{"name": "subagent_tool_1", "args": {}}],
        }
        int_obj2 = Mock()
        int_obj2.id = "int_subagent_2"
        int_obj2.value = {
            "action_requests": [{"name": "subagent_tool_2", "args": {}}],
        }
        yield ((), "updates", {"__interrupt__": [int_obj1, int_obj2]})

    adapter._client.astream = mock_astream

    await adapter.stream_turn(prompt="Test", thread_id="t1")

    assert approval_counts == 2
    assert captured_resume == {
        "int_subagent_1": {"decisions": [{"type": "approve"}]},
        "int_subagent_2": {"decisions": [{"type": "approve"}]},
    }


@pytest.mark.asyncio
async def test_textual_adapter_interrupt_auto_approve_flag():
    """Verify that auto_approve=True bypasses _request_approval and auto-approves."""
    mock_request_approval = AsyncMock()

    adapter = TextualAdapter(
        app=MagicMock(),
        client=MagicMock(),
        assistant_id="mock_id",
        status_bar=MagicMock(),
        auto_approve=True,
        request_approval=mock_request_approval,
    )

    captured_resume = None

    async def mock_astream(stream_input, *args, **kwargs):
        nonlocal captured_resume
        if isinstance(stream_input, Command) and stream_input.resume:
            captured_resume = stream_input.resume
            return

        interrupt_obj = Mock()
        interrupt_obj.id = "int_auto_flag"
        interrupt_obj.value = {
            "action_requests": [{"name": "write_file", "args": {}}],
        }
        yield ((), "updates", {"__interrupt__": [interrupt_obj]})

    adapter._client.astream = mock_astream

    await adapter.stream_turn(prompt="Test", thread_id="t1")

    mock_request_approval.assert_not_called()
    assert captured_resume == {
        "int_auto_flag": {"decisions": [{"type": "approve"}]}
    }


@pytest.mark.asyncio
async def test_textual_adapter_interrupt_fallback():
    """Verify backwards-compatible fallback when request_approval is None."""
    mock_app = Mock(spec=["post_message"])

    adapter = TextualAdapter(
        app=mock_app,
        client=MagicMock(),
        assistant_id="mock_id",
        status_bar=MagicMock(),
        request_approval=None,
    )
    # Mock fallback _await_approval
    adapter._await_approval = AsyncMock(return_value=True)

    captured_resume = None

    async def mock_astream(stream_input, *args, **kwargs):
        nonlocal captured_resume
        if isinstance(stream_input, Command) and stream_input.resume:
            captured_resume = stream_input.resume
            return

        interrupt_obj = Mock()
        interrupt_obj.id = "int_fallback"
        interrupt_obj.value = {
            "action_requests": [{"name": "write_file", "args": {}}],
        }
        yield ((), "updates", {"__interrupt__": [interrupt_obj]})

    adapter._client.astream = mock_astream

    await adapter.stream_turn(prompt="Test", thread_id="t1")

    adapter._await_approval.assert_called_once_with("int_fallback_0")
    assert captured_resume == {
        "int_fallback": {"decisions": [{"type": "approve"}]}
    }
