"""Classifier-backed approval policy middleware for the local interactive runtime."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.human_in_the_loop import (
    HumanInTheLoopMiddleware,
    InterruptOnConfig,
)
from langchain.agents.middleware.types import (
    AgentState,
    ExtendedModelResponse,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
)
import uuid

USER_PROMPT_METADATA_KEY = "deepagents_code_user_prompt"


def user_prompt_metadata(
    literal_user_text: str,
    referenced_paths: list[str] | None = None,
    turn_id: str | None = None,
) -> dict[str, Any]:
    return {
        "literal_user_text": literal_user_text,
        "referenced_paths": list(referenced_paths or []),
        "turn_id": turn_id or str(uuid.uuid4()),
    }


from langchain_core.messages import AIMessage
from langgraph.types import Command
from dcoder.middleware.registry import register_middleware

logger = logging.getLogger("dcoder")


@register_middleware(name="auto_mode_hitl")
class AutoModeHITLMiddleware(HumanInTheLoopMiddleware[AgentState[Any], Any, Any]):
    """Classifier-backed approval policy middleware for dynamic tool call decisions."""

    @property
    def name(self) -> str:
        return HumanInTheLoopMiddleware.__name__

    def __init__(
        self,
        interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
        *,
        worktree_root: Any | None = None,
        shell_allow_list: list[str] | None = None,
    ) -> None:
        super().__init__(interrupt_on or {})
        self._worktree_root = worktree_root
        self._shell_allow_list = shell_allow_list or []

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any] | ExtendedModelResponse[Any]:
        response = await handler(request)
        ai_message = next(
            (
                message
                for message in reversed(response.result)
                if isinstance(message, AIMessage)
            ),
            None,
        )
        if ai_message is None or not getattr(ai_message, "tool_calls", None):
            return ExtendedModelResponse(
                model_response=response,
                command=Command(update={"_auto_decision_plan": None}),
            )

        calls = list(getattr(ai_message, "tool_calls", []))
        gated_calls = [call for call in calls if call and isinstance(call, dict) and call.get("name") in self.interrupt_on]
        if not gated_calls:
            return response

        return ExtendedModelResponse(
            model_response=response,
            command=Command(
                update={
                    "_auto_decision_plan": {
                        "batch_id": f"batch-{len(calls)}",
                        "gated_calls_count": len(gated_calls),
                    }
                }
            ),
        )

    async def aafter_model(
        self,
        state: AgentState[Any],
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        ai_message = next(
            (
                message
                for message in reversed(state.get("messages") or [])
                if isinstance(message, AIMessage)
            ),
            None,
        )
        logger.debug(
            "[HITL_TRACE_DEBUG] AutoModeHITLMiddleware.aafter_model invoked | messages_count=%d | tool_calls=%s",
            len(state.get("messages") or []),
            getattr(ai_message, "tool_calls", None),
        )
        if ai_message is None or not getattr(ai_message, "tool_calls", None):
            return {"_auto_decision_plan": None}

        mode = await _aresolve_approval_mode(runtime.context, runtime.store)
        routed_state = dict(state)
        routed_state[_ASYNC_APPROVAL_ROUTING_KEY] = _RoutingDecision(mode)
        res = super().after_model(cast(AgentState[Any], routed_state), runtime)
        if res is not None:
            res["_auto_decision_plan"] = None
            return res
        return {"_auto_decision_plan": None}

    def after_model(
        self,
        state: AgentState[Any],
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        return super().after_model(state, runtime)


from dataclasses import dataclass
from collections.abc import Mapping
from typing import cast
from langgraph.runtime import Runtime
from dcoder.security.approval_mode import (
    ApprovalMode,
    approval_mode_key,
    aread_approval_mode_from_store,
)

_ASYNC_APPROVAL_ROUTING_KEY = "_dcoder_async_approval_routing"


@dataclass(frozen=True)
class _RoutingDecision:
    """A trusted in-process approval decision from the async read hook."""

    mode: ApprovalMode


@dataclass(frozen=True)
class _DecidedMode:
    mode: ApprovalMode


@dataclass(frozen=True)
class _UndecidedModeSource:
    key: str


def _approval_mode_source(context: object) -> _DecidedMode | _UndecidedModeSource:
    if isinstance(context, Mapping):
        thread_id = context.get("thread_id")
        if isinstance(thread_id, str) and thread_id:
            return _UndecidedModeSource(approval_mode_key(thread_id))
    return _DecidedMode(ApprovalMode.MANUAL)


async def _aresolve_approval_mode(context: object, store: object) -> ApprovalMode:
    source = _approval_mode_source(context)
    if isinstance(source, _DecidedMode):
        return source.mode
    mode = await aread_approval_mode_from_store(store, source.key)
    if mode is None:
        return ApprovalMode.MANUAL
    return mode


def _async_routing_mode(state: object) -> ApprovalMode | None:
    """Return a mode resolved by the async HITL hook in this call only."""
    if isinstance(state, dict):
        routed = state.get(_ASYNC_APPROVAL_ROUTING_KEY)
        if isinstance(routed, _RoutingDecision):
            return routed.mode
    return None


@register_middleware(name="async_approval_hitl")
class AsyncApprovalHITLMiddleware(HumanInTheLoopMiddleware[Any, Any, Any]):
    """Stock HITL routing with an async live-mode read after model completion."""

    @property
    def name(self) -> str:
        return HumanInTheLoopMiddleware.__name__

    def __init__(
        self,
        interrupt_on: Mapping[str, bool | InterruptOnConfig],
    ) -> None:
        super().__init__(dict(interrupt_on))

    async def aafter_model(
        self,
        state: AgentState[Any],
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        mode = await _aresolve_approval_mode(runtime.context, runtime.store)
        logger.debug(
            "[HITL_TRACE_DEBUG] AsyncApprovalHITLMiddleware.aafter_model invoked | mode=%s | state_keys=%s",
            mode,
            list(state.keys()) if isinstance(state, dict) else [],
        )
        routed_state = dict(state)
        routed_state[_ASYNC_APPROVAL_ROUTING_KEY] = _RoutingDecision(mode)
        return super().after_model(cast(AgentState[Any], routed_state), runtime)

    def after_model(
        self,
        state: AgentState[Any],
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        logger.warning(
            "AsyncApprovalHITLMiddleware ran synchronously; live autonomous "
            "modes will not take effect and gated calls fall back to Manual"
        )
        return super().after_model(state, runtime)
