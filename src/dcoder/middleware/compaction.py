"""CLI conversation compaction middleware for context window optimization."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated, Any, cast

from langchain.agents.middleware.types import AgentMiddleware, AgentState, ToolCallRequest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import InjectedToolArg, StructuredTool, tool
from langgraph.types import Command

from dcoder.middleware.registry import register_middleware
from dcoder.offload import _offload_fallback_root

logger = logging.getLogger("dcoder")

COMPACTION_FAILURE_PREFIX = "Compaction failed"
_OFFLOAD_SEED_ID_PREFIX = "offload-seed-"


def _offload_seed_message_id(tool_call_id: str) -> str:
    return f"{_OFFLOAD_SEED_ID_PREFIX}{tool_call_id}"


def _without_offload_seed(messages: list[Any], tool_call_id: str) -> list[Any]:
    if not tool_call_id:
        return messages
    seed_id = _offload_seed_message_id(tool_call_id)
    return [
        m
        for m in messages
        if (m.get("id") if isinstance(m, dict) else getattr(m, "id", None)) != seed_id
    ]


@register_middleware(name="compaction")
class CLICompactionMiddleware(AgentMiddleware[Any, Any]):
    """Compacts conversation history when message token/line limits approach."""

    def __init__(
        self,
        *,
        max_message_lines: int = 1500,
        thread_id: str | None = None,
    ) -> None:
        super().__init__()
        self._max_message_lines = max_message_lines
        self._thread_id = thread_id
        self.tools = [self._create_compact_tool()]

    def _create_compact_tool(self) -> StructuredTool:
        middleware = self

        def sync_compact(
            force: Annotated[bool, InjectedToolArg] = False,
            tool_call_id: str = "",
            state: Any = None,
        ) -> Command[Any]:
            del force
            return middleware._run_forced_compact(state=state, tool_call_id=tool_call_id)

        async def async_compact(
            force: Annotated[bool, InjectedToolArg] = False,
            tool_call_id: str = "",
            state: Any = None,
        ) -> Command[Any]:
            del force
            return middleware._run_forced_compact(state=state, tool_call_id=tool_call_id)

        return StructuredTool.from_function(
            name="compact_conversation",
            description=(
                "Compact the conversation by summarizing older messages into a concise summary."
            ),
            func=sync_compact,
            coroutine=async_compact,
        )

    def _offload_archive_path(self, thread_id: str) -> Path:
        archive_dir = _offload_fallback_root() / "conversation_history"
        archive_dir.mkdir(parents=True, exist_ok=True)
        return archive_dir / f"{thread_id}.md"

    def compact_history(self, messages: list[Any], thread_id: str | None = None) -> list[Any]:
        """Summarize and compact old messages if history exceeds limits."""
        if len(messages) <= 6:
            return messages

        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        recent_msgs = messages[-6:]
        old_msgs = messages[len(system_msgs):-6]

        if not old_msgs:
            return messages

        active_thread = thread_id or self._thread_id
        if active_thread:
            archive_path = self._offload_archive_path(active_thread)
            try:
                archive_text = "\n\n".join([f"**{type(m).__name__}**: {m.content}" for m in old_msgs])
                with archive_path.open("a", encoding="utf-8") as f:
                    f.write(f"\n\n--- Compacted History ---\n{archive_text}")
            except OSError:
                logger.warning("Failed writing offloaded history to %s", archive_path, exc_info=True)

        summary_content = (
            f"[Compacted Conversation History: {len(old_msgs)} prior intermediate messages offloaded. "
            "Recent turns retained below.]"
        )
        summary_msg = SystemMessage(content=summary_content)

        return [*system_msgs, summary_msg, *recent_msgs]

    def _run_forced_compact(self, state: Any, tool_call_id: str = "") -> Command[Any]:
        try:
            messages = list(state.get("messages") or []) if state else []
            compacted = self.compact_history(messages)
            return Command(update={"messages": compacted})
        except Exception as exc:
            logger.exception("forced compact_conversation failed")
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                f"{COMPACTION_FAILURE_PREFIX}: an error occurred "
                                f"during compaction ({type(exc).__name__}: {exc}). "
                                "Your conversation is unchanged."
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

    def before_agent(self, state: AgentState[Any], runtime: Any = None, config: Any = None) -> Any:
        messages = list(state.get("messages") or [])
        total_lines = sum(str(m.content).count("\n") + 1 for m in messages if hasattr(m, "content"))

        if total_lines > self._max_message_lines or len(messages) > 30:
            compacted = self.compact_history(messages)
            return {"messages": compacted}

        return None

    async def abefore_agent(self, state: AgentState[Any], runtime: Any = None, config: Any = None) -> Any:
        import asyncio
        return await asyncio.to_thread(self.before_agent, state, runtime, config)


    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        return await handler(request)

    def wrap_model_call(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        return handler(request)

    async def awrap_model_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        return await handler(request)

