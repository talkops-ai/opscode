import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock
import pytest
from langgraph.types import Command
from opscode.ui.textual_adapter import TextualAdapter


@pytest.mark.asyncio
async def test_resolve_pending_interrupts_handles_ask_user_answered():
    """Verify that ask_user interrupt resolves to answered payload with user answers."""
    loop = asyncio.get_running_loop()
    expected_answers = ["S3 with SSE-KMS", "Enable bucket versioning"]

    async def mock_request_ask_user(questions):
        assert len(questions) == 2
        fut = loop.create_future()
        fut.set_result({"type": "answered", "answers": expected_answers})
        return fut

    adapter = TextualAdapter(
        app=MagicMock(),
        client=MagicMock(),
        assistant_id="opscode",
        request_ask_user=mock_request_ask_user,
    )

    pending_interrupts = {
        "interrupt_1": {
            "type": "ask_user",
            "questions": [
                {
                    "question": "Select encryption",
                    "type": "multiple_choice",
                    "choices": [{"value": "SSE-KMS"}],
                },
                {"question": "Enable versioning?", "type": "multiple_choice", "choices": [{"value": "Yes"}]},
            ],
            "tool_call_id": "call_abc123",
        }
    }

    resume_payload = await adapter._resolve_pending_interrupts(pending_interrupts)

    assert "interrupt_1" in resume_payload
    assert resume_payload["interrupt_1"]["status"] == "answered"
    assert resume_payload["interrupt_1"]["answers"] == expected_answers


@pytest.mark.asyncio
async def test_resolve_pending_interrupts_handles_ask_user_cancellation():
    """Verify that ask_user interrupt resolves to cancelled payload when user cancels."""
    loop = asyncio.get_running_loop()

    async def mock_request_ask_user(questions):
        fut = loop.create_future()
        fut.set_result({"type": "cancelled"})
        return fut

    adapter = TextualAdapter(
        app=MagicMock(),
        client=MagicMock(),
        assistant_id="opscode",
        request_ask_user=mock_request_ask_user,
    )

    pending_interrupts = {
        "interrupt_2": {
            "type": "ask_user",
            "questions": [{"question": "Confirm plan", "type": "text"}],
            "tool_call_id": "call_xyz",
        }
    }

    resume_payload = await adapter._resolve_pending_interrupts(pending_interrupts)

    assert "interrupt_2" in resume_payload
    assert resume_payload["interrupt_2"]["status"] == "cancelled"
    assert resume_payload["interrupt_2"]["answers"] == ["(cancelled)"]


@pytest.mark.asyncio
async def test_resolve_pending_interrupts_handles_ask_user_headless_fallback():
    """Verify headless/non-interactive fallback when request_ask_user is not provided."""
    adapter = TextualAdapter(
        app=None,
        client=MagicMock(),
        assistant_id="opscode",
        request_ask_user=None,
    )

    pending_interrupts = {
        "interrupt_headless": {
            "type": "ask_user",
            "questions": [{"question": "Enter API token", "type": "text"}],
            "tool_call_id": "call_token",
        }
    }

    resume_payload = await adapter._resolve_pending_interrupts(pending_interrupts)

    assert "interrupt_headless" in resume_payload
    assert resume_payload["interrupt_headless"]["status"] == "cancelled"
    assert "not supported" in resume_payload["interrupt_headless"]["error"]
    assert resume_payload["interrupt_headless"]["answers"] == ["(cancelled)"]


@pytest.mark.asyncio
async def test_resolve_pending_interrupts_handles_ask_user_exception():
    """Verify error status when request_ask_user raises an exception."""
    async def mock_request_ask_user_error(questions):
        raise RuntimeError("Widget mount failed")

    adapter = TextualAdapter(
        app=MagicMock(),
        client=MagicMock(),
        assistant_id="opscode",
        request_ask_user=mock_request_ask_user_error,
    )

    pending_interrupts = {
        "interrupt_err": {
            "type": "ask_user",
            "questions": [{"question": "Choice?", "type": "text"}],
            "tool_call_id": "call_err",
        }
    }

    resume_payload = await adapter._resolve_pending_interrupts(pending_interrupts)

    assert "interrupt_err" in resume_payload
    assert resume_payload["interrupt_err"]["status"] == "error"
    assert "Widget mount failed" in resume_payload["interrupt_err"]["error"]


@pytest.mark.asyncio
async def test_resolve_pending_interrupts_mixed_segregation():
    """Verify that ask_user interrupts and action_requests approvals are cleanly segregated."""
    loop = asyncio.get_running_loop()

    async def mock_request_approval(action_requests, assistant_id):
        fut = loop.create_future()
        fut.set_result({"type": "approve"})
        return fut

    async def mock_request_ask_user(questions):
        fut = loop.create_future()
        fut.set_result({"type": "answered", "answers": ["Custom answer"]})
        return fut

    adapter = TextualAdapter(
        app=MagicMock(),
        client=MagicMock(),
        assistant_id="opscode",
        request_approval=mock_request_approval,
        request_ask_user=mock_request_ask_user,
    )

    pending_interrupts = {
        "int_ask": {
            "type": "ask_user",
            "questions": [{"question": "Strategy?", "type": "text"}],
            "tool_call_id": "call_strategy",
        },
        "int_hitl": {
            "action_requests": [{"name": "terraform_apply", "args": {}}],
        },
    }

    resume_payload = await adapter._resolve_pending_interrupts(pending_interrupts)

    assert "int_ask" in resume_payload
    assert resume_payload["int_ask"]["status"] == "answered"
    assert resume_payload["int_ask"]["answers"] == ["Custom answer"]

    assert "int_hitl" in resume_payload
    assert resume_payload["int_hitl"]["decisions"] == [{"type": "approve"}]


@pytest.mark.asyncio
async def test_auto_approve_does_not_bypass_ask_user():
    """Verify that auto_approve=True auto-approves actions but still prompts user for ask_user questions."""
    loop = asyncio.get_running_loop()
    ask_user_called = False

    async def mock_request_ask_user(questions):
        nonlocal ask_user_called
        ask_user_called = True
        fut = loop.create_future()
        fut.set_result({"type": "answered", "answers": ["Option A"]})
        return fut

    adapter = TextualAdapter(
        app=MagicMock(),
        client=MagicMock(),
        assistant_id="opscode",
        auto_approve=True,
        request_ask_user=mock_request_ask_user,
    )

    pending_interrupts = {
        "int_ask": {
            "type": "ask_user",
            "questions": [{"question": "Option?", "type": "text"}],
            "tool_call_id": "call_opt",
        },
        "int_hitl": {
            "action_requests": [{"name": "shell_exec", "args": {}}],
        },
    }

    resume_payload = await adapter._resolve_pending_interrupts(pending_interrupts)

    assert ask_user_called is True
    assert resume_payload["int_ask"]["answers"] == ["Option A"]
    assert resume_payload["int_hitl"]["decisions"] == [{"type": "approve"}]


@pytest.mark.asyncio
async def test_stream_turn_with_ask_user_interrupt_flow():
    """End-to-end stream_turn verifying that an ask_user interrupt sends the resume payload."""
    loop = asyncio.get_running_loop()

    async def mock_request_ask_user(questions):
        fut = loop.create_future()
        fut.set_result({"type": "answered", "answers": ["us-west-2"]})
        return fut

    adapter = TextualAdapter(
        app=MagicMock(),
        client=MagicMock(),
        assistant_id="opscode",
        status_bar=MagicMock(),
        request_ask_user=mock_request_ask_user,
    )

    captured_resume = None

    async def mock_astream(stream_input, *args, **kwargs):
        nonlocal captured_resume
        if isinstance(stream_input, Command) and stream_input.resume:
            captured_resume = stream_input.resume
            return

        interrupt_obj = Mock()
        interrupt_obj.id = "int_ask_region"
        interrupt_obj.value = {
            "type": "ask_user",
            "questions": [{"question": "Target AWS Region?", "type": "text"}],
            "tool_call_id": "call_reg_1",
        }
        yield ((), "updates", {"__interrupt__": [interrupt_obj]})

    adapter._client.astream = mock_astream

    await adapter.stream_turn(prompt="Deploy to AWS", thread_id="t1")

    assert captured_resume == {
        "int_ask_region": {
            "status": "answered",
            "answers": ["us-west-2"],
        }
    }
