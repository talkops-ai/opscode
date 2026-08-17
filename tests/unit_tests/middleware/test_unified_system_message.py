"""Unit tests for UnifiedSystemMessageMiddleware and unify_system_message."""

from typing import Any, cast
import pytest
from langchain_core.messages import SystemMessage
from langchain.agents.middleware.types import ModelRequest, ModelResponse

from opscode.middleware.unified_system_message import (
    UnifiedSystemMessageMiddleware,
    unify_system_message,
)


def test_unify_system_message_none() -> None:
    assert unify_system_message(None) is None


def test_unify_system_message_string_content() -> None:
    msg = SystemMessage(content="You are an agent.")
    unified = unify_system_message(msg)
    assert unified is not None
    assert unified is msg
    assert isinstance(unified.content, str)
    assert unified.content == "You are an agent."


def test_unify_system_message_list_blocks() -> None:
    raw_blocks: list[dict[str, Any] | str] = [
        {"type": "text", "text": "You are the **Terraform Linter**."},
        {"type": "text", "text": "\n\n## Shell paths vs virtual paths\n\nSome paths..."},
        {"type": "text", "text": "\n\n## Skills System\n\n- **tf-validate**..."},
    ]
    msg = SystemMessage(content=cast(Any, raw_blocks))
    unified = unify_system_message(msg)
    assert unified is not None
    assert isinstance(unified.content, str)
    assert "You are the **Terraform Linter**." in unified.content
    assert "## Shell paths vs virtual paths" in unified.content
    assert "## Skills System" in unified.content


def test_middleware_wrap_model_call() -> None:
    mw = UnifiedSystemMessageMiddleware()
    raw_blocks: list[dict[str, Any] | str] = [
        {"type": "text", "text": "Base prompt."},
        {"type": "text", "text": "\n\nInjected context."},
    ]
    orig_msg = SystemMessage(content=cast(Any, raw_blocks))
    req = ModelRequest(
        model=cast(Any, "test-model"),
        system_message=orig_msg,
        messages=[],
        tools=[],
        state=cast(Any, {}),
        runtime=None,  # type: ignore[arg-type]
    )

    captured_req: ModelRequest | None = None

    def dummy_handler(request: ModelRequest) -> ModelResponse:
        nonlocal captured_req
        captured_req = request
        return ModelResponse(result=None)  # type: ignore[arg-type]

    mw.wrap_model_call(req, dummy_handler)

    assert captured_req is not None
    assert captured_req.system_message is not None
    assert isinstance(captured_req.system_message.content, str)
    assert captured_req.system_message.content == "Base prompt.\n\nInjected context."


@pytest.mark.asyncio
async def test_middleware_awrap_model_call() -> None:
    mw = UnifiedSystemMessageMiddleware()
    raw_blocks: list[dict[str, Any] | str] = [
        {"type": "text", "text": "Async Base prompt."},
        {"type": "text", "text": "\n\nAsync Injected context."},
    ]
    orig_msg = SystemMessage(content=cast(Any, raw_blocks))
    req = ModelRequest(
        model=cast(Any, "test-model"),
        system_message=orig_msg,
        messages=[],
        tools=[],
        state=cast(Any, {}),
        runtime=None,  # type: ignore[arg-type]
    )

    captured_req: ModelRequest | None = None

    async def dummy_async_handler(request: ModelRequest) -> ModelResponse:
        nonlocal captured_req
        captured_req = request
        return ModelResponse(result=None)  # type: ignore[arg-type]

    await mw.awrap_model_call(req, dummy_async_handler)

    assert captured_req is not None
    assert captured_req.system_message is not None
    assert isinstance(captured_req.system_message.content, str)
    assert captured_req.system_message.content == "Async Base prompt.\n\nAsync Injected context."
