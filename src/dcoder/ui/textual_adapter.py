"""Stream bridge between LangGraph SDK client and Textual widgets.

The ``TextualAdapter`` consumes streaming events from ``client.runs.stream()``
and routes them to the main application and widgets using thread-safe Textual
events.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from enum import Enum
from typing import TYPE_CHECKING, Any

from textual.message import Message

if TYPE_CHECKING:
    from dcoder.ui.messages import MessageList
    from dcoder.ui.status import StatusBar

logger = logging.getLogger(__name__)


def _format_thinking_tags(text: str) -> str:
    """Format inline <thinking> or <thought> XML tags into blockquotes."""
    if not text:
        return text
    text = text.replace("<thinking>", "> *Thinking:*\n> ").replace("</thinking>", "\n\n")
    text = text.replace("<thought>", "> *Thinking:*\n> ").replace("</thought>", "\n\n")
    return text


def _format_thinking_quote(text: str) -> str:
    """Format a thinking string cleanly into blockquote format."""
    if not text:
        return ""
    clean = text.strip()
    if not clean:
        return ""
    return f"> *Thinking:* {clean}\n\n"


def _extract_text_and_thinking(
    content: Any,
    additional_kwargs: dict[str, Any] | None = None,
    response_metadata: dict[str, Any] | None = None,
    msg_obj: Any = None,
) -> tuple[str, str]:
    """Extract regular response text and internal thinking/reasoning text from message.

    Returns:
        (text, thinking_text)
    """
    text_parts: list[str] = []
    thinking_parts: list[str] = []

    # 1. Direct reasoning attributes on message object (DeepSeek / Anthropic / Gemini / LangChain)
    if msg_obj is not None:
        direct_thinking = (
            getattr(msg_obj, "reasoning_content", None)
            or getattr(msg_obj, "thinking", None)
            or getattr(msg_obj, "thoughts", None)
        )
        if direct_thinking and isinstance(direct_thinking, str):
            thinking_parts.append(direct_thinking)

    # 2. Additional kwargs and response metadata
    combined: dict[str, Any] = {}
    if additional_kwargs and isinstance(additional_kwargs, dict):
        combined.update(additional_kwargs)
    if response_metadata and isinstance(response_metadata, dict):
        combined.update(response_metadata)

    thinking = (
        combined.get("thinking")
        or combined.get("thoughts")
        or combined.get("reasoning_content")
        or combined.get("thought")
    )
    if thinking:
        if isinstance(thinking, str):
            thinking_parts.append(thinking)
        elif isinstance(thinking, dict) and isinstance(thinking.get("text"), str):
            thinking_parts.append(thinking["text"])
        elif isinstance(thinking, list):
            for t_item in thinking:
                if isinstance(t_item, str):
                    thinking_parts.append(t_item)
                elif isinstance(t_item, dict) and isinstance(t_item.get("text"), str):
                    thinking_parts.append(t_item["text"])

    # 3. Content blocks & string parsing
    if isinstance(content, str):
        if "<thinking>" in content or "<thought>" in content:
            raw = content
            for tag_open, tag_close in [("<thinking>", "</thinking>"), ("<thought>", "</thought>")]:
                while tag_open in raw:
                    start = raw.find(tag_open)
                    end = raw.find(tag_close, start)
                    if end != -1:
                        think_chunk = raw[start + len(tag_open) : end]
                        thinking_parts.append(think_chunk)
                        raw = raw[:start] + raw[end + len(tag_close) :]
                    else:
                        think_chunk = raw[start + len(tag_open) :]
                        thinking_parts.append(think_chunk)
                        raw = raw[:start]
            if raw:
                text_parts.append(raw)
        elif content:
            text_parts.append(content)
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict):
                block_type = block.get("type", "")
                think_val = (
                    block.get("thinking")
                    or block.get("thoughts")
                    or block.get("reasoning")
                    or block.get("reasoning_content")
                )
                if think_val:
                    if isinstance(think_val, str):
                        thinking_parts.append(think_val)
                    elif isinstance(think_val, dict) and isinstance(think_val.get("text"), str):
                        thinking_parts.append(think_val["text"])
                elif block_type in ("thinking", "thought", "reasoning"):
                    text_val = block.get("text") or block.get("thinking") or block.get("thought")
                    if text_val and isinstance(text_val, str):
                        thinking_parts.append(text_val)
                elif isinstance(block.get("text"), str):
                    text_parts.append(block["text"])
            elif hasattr(block, "text") and isinstance(getattr(block, "text"), str):
                text_parts.append(getattr(block, "text"))
    elif content is not None:
        text_parts.append(str(content))

    return "".join(text_parts), "".join(thinking_parts)


def _extract_text(
    content: Any,
    additional_kwargs: dict[str, Any] | None = None,
    response_metadata: dict[str, Any] | None = None,
    msg_obj: Any = None,
) -> str:
    """Extract string text from a message content string, list, or block structure (including thinking/reasoning blocks)."""
    text, thinking = _extract_text_and_thinking(content, additional_kwargs, response_metadata, msg_obj)
    if thinking:
        return f"> *Thinking:* {thinking}\n\n{text}"
    return text


class ToolLifecycleState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class ToolState:
    call_id: str
    name: str
    args: dict[str, Any]
    state: ToolLifecycleState = ToolLifecycleState.PENDING
    result: Any = None
    error: str | None = None


@dataclass
class SessionStats:
    """Accumulated stats for the current session."""

    input_tokens: int = 0
    output_tokens: int = 0
    request_count: int = 0
    model: str = ""
    tool_calls: int = 0
    elapsed_seconds: float = 0.0


class TextualAdapter:
    """Bridge between LangGraph SDK stream events and Textual widgets.

    Parses the event stream from ``client.runs.stream()`` and posts custom
    Textual events for thread-safe UI rendering and lifecycle tracking.
    """

    # ── Custom Textual Events ────────────────────────────

    class TokenStreamed(Message):
        def __init__(self, token: str) -> None:
            super().__init__()
            self.token = token

    class ToolCallStarted(Message):
        def __init__(self, name: str, call_id: str, args: dict[str, Any]) -> None:
            super().__init__()
            self.name = name
            self.call_id = call_id
            self.args = args

    class ToolCallCompleted(Message):
        def __init__(
            self, call_id: str, result: Any, status: ToolLifecycleState
        ) -> None:
            super().__init__()
            self.call_id = call_id
            self.result = result
            self.status = status

    class InterruptRaised(Message):
        def __init__(
            self,
            tool_name: str,
            call_id: str,
            args: dict[str, Any],
            interrupt_type: str = "tool_approval",
        ) -> None:
            super().__init__()
            self.tool_name = tool_name
            self.call_id = call_id
            self.args = args
            self.interrupt_type = interrupt_type

    class SubagentSpawned(Message):
        def __init__(self, agent_name: str, task: str) -> None:
            super().__init__()
            self.agent_name = agent_name
            self.task = task

    class SubagentUpdate(Message):
        def __init__(self, agent_name: str, token: str, status: str = "running") -> None:
            super().__init__()
            self.agent_name = agent_name
            self.token = token
            self.status = status

    class StreamFinished(Message):
        def __init__(self, stats: SessionStats) -> None:
            super().__init__()
            self.stats = stats

    class StreamError(Message):
        def __init__(self, error: str) -> None:
            super().__init__()
            self.error = error

    def __init__(
        self,
        *,
        client: Any,
        assistant_id: str,
        messages_widget: MessageList | None = None,
        status_bar: StatusBar | None = None,
        auto_approve: bool = False,
        set_spinner: Any = None,
        app: Any = None,
    ) -> None:
        self._client = client
        self._assistant_id = assistant_id
        self._messages: MessageList | None = messages_widget
        self._status_bar: StatusBar | None = status_bar
        self._auto_approve = auto_approve
        self._set_spinner = set_spinner
        self._app = app
        self._stats = SessionStats()
        self._cancel_event = asyncio.Event()
        self._active_tools: dict[str, ToolState] = {}
        self._active_tools_map: dict[str, str] = {}
        self._approval_events: dict[str, asyncio.Event] = {}
        self._approval_responses: dict[str, bool] = {}

    @property
    def stats(self) -> SessionStats:
        return self._stats

    @property
    def connected(self) -> bool:
        """Return True when a client is bound and ready for streaming."""
        return self._client is not None

    def set_client(self, client: Any) -> None:
        """Bind or replace the LangGraph SDK client (deferred server startup).

        Called by ``DCoderApp`` when the background server worker posts
        ``ServerReady``.  After this call, ``stream_turn`` can execute.
        """
        self._client = client

    # ── Public Stream API ─────────────────────────────────

    async def stream_turn(
        self,
        prompt: str,
        *,
        thread_id: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Run one agent turn, routing stream events to Textual widgets."""
        from langchain_core.messages import AIMessageChunk, ToolMessage

        self._cancel_event.clear()
        self._active_tools.clear()
        self._active_tools_map.clear()

        if self._status_bar is not None:
            self._status_bar.set_status("Thinking...")
        if self._set_spinner:
            await self._set_spinner("Thinking")

        input_msg: dict[str, Any] = {"messages": [{"role": "user", "content": prompt}]}

        if self._app is not None:
            from dcoder.commands.power.goal import get_goal_state, GoalHandler
            goal_state = get_goal_state(self._app)
            if goal_state.is_actionable and goal_state.objective:
                input_msg["_goal_objective"] = goal_state.objective
                input_msg["_goal_rubric"] = goal_state.rubric
                input_msg["_goal_status"] = goal_state.status
                if goal_state.rubric:
                    input_msg["rubric"] = goal_state.rubric
            elif goal_state.next_rubric:
                input_msg["rubric"] = goal_state.next_rubric
                goal_state.next_rubric = None  # One-turn quality gate
                GoalHandler._sync_status_rubric(self._app, goal_state)
            elif goal_state.rubric:
                input_msg["_sticky_rubric"] = goal_state.rubric
                input_msg["rubric"] = goal_state.rubric
        config = {"configurable": {"thread_id": thread_id}}
        logger.debug("TUI: stream_turn start, thread_id: %s, context: %s", thread_id, context)

        start_t = time.time()
        self._stats.input_tokens += max(1, len(prompt) // 4)
        if self._status_bar is not None:
            self._status_bar.update_stats(self._stats)

        current_thinking_widget: Any | None = None
        thinking_start_t: float | None = None
        accumulated_thinking = ""

        try:
            if self._messages is not None:
                self._messages.start_assistant_message()

            logger.debug("TUI: calling agent.astream...")

            async for chunk in self._client.astream(
                input_msg,
                stream_mode=["messages", "updates", "custom"],
                subgraphs=True,
                config=config,
                context=context,
            ):
                if self._cancel_event.is_set():
                    logger.debug("TUI: cancel event is set, breaking stream loop")
                    break

                if not isinstance(chunk, tuple) or len(chunk) != 3:
                    continue

                namespace, mode, data = chunk

                if mode == "messages":
                    msg_obj, meta = data if isinstance(data, tuple) else (data, {})
                    if isinstance(msg_obj, AIMessageChunk):
                        usage_meta = (
                            getattr(msg_obj, "usage_metadata", None)
                            or (getattr(msg_obj, "response_metadata", None) or {}).get("usage")
                            or (getattr(msg_obj, "response_metadata", None) or {}).get("token_usage")
                            or (meta or {}).get("usage")
                        )
                        if isinstance(usage_meta, dict):
                            inp_toks = usage_meta.get("input_tokens") or usage_meta.get("prompt_tokens") or 0
                            out_toks = usage_meta.get("output_tokens") or usage_meta.get("completion_tokens") or 0
                            if inp_toks > 0:
                                self._stats.input_tokens = inp_toks
                            if out_toks > 0:
                                self._stats.output_tokens = out_toks
                            if inp_toks > 0 or out_toks > 0:
                                context_toks = (inp_toks or 0) + (out_toks or 0)
                                if self._app:
                                    setattr(self._app, "_context_tokens", context_toks)
                                if self._status_bar is not None:
                                    self._status_bar.update_stats(self._stats)

                        text, thinking_text = _extract_text_and_thinking(
                            msg_obj.content,
                            getattr(msg_obj, "additional_kwargs", None),
                            getattr(msg_obj, "response_metadata", None),
                            msg_obj=msg_obj,
                        )

                        if thinking_text:
                            if current_thinking_widget is None:
                                thinking_start_t = time.time()
                                if self._messages is not None:
                                    current_thinking_widget = self._messages.add_thinking_message()
                            accumulated_thinking += thinking_text
                            if current_thinking_widget and thinking_start_t is not None:
                                dur = time.time() - thinking_start_t
                                current_thinking_widget.update_thinking(accumulated_thinking, duration_seconds=dur)

                        if text:
                            if current_thinking_widget is not None and thinking_start_t is not None:
                                dur = time.time() - thinking_start_t
                                current_thinking_widget.update_thinking(accumulated_thinking, duration_seconds=dur)
                                current_thinking_widget = None
                                thinking_start_t = None
                                accumulated_thinking = ""

                            if self._messages is not None:
                                self._messages.append_assistant_token(text)
                            if self._app:
                                self._app.post_message(self.TokenStreamed(text))

                        tool_calls = getattr(msg_obj, "tool_calls", []) or []
                        if tool_calls:
                            if current_thinking_widget is not None and thinking_start_t is not None:
                                dur = time.time() - thinking_start_t
                                current_thinking_widget.update_thinking(accumulated_thinking, duration_seconds=dur)
                                current_thinking_widget = None
                                thinking_start_t = None
                                accumulated_thinking = ""

                            if self._messages is not None:
                                self._messages.finish_assistant_message()
                        for tc in tool_calls:
                            call_id = tc.get("id", "") or ""
                            raw_name = tc.get("name") or ""
                            name = raw_name if (raw_name and raw_name != "None") else "tool"
                            args = tc.get("args", {}) or {}
                            if call_id:
                                self._active_tools_map[call_id] = name
                            self._stats.tool_calls += 1
                            if self._messages is not None:
                                self._messages.add_tool_call(name=name, call_id=call_id, args=args)
                            if self._app:
                                self._app.post_message(self.ToolCallStarted(name, call_id, args))

                    elif isinstance(msg_obj, ToolMessage):
                        call_id = getattr(msg_obj, "tool_call_id", "") or ""
                        raw_name = getattr(msg_obj, "name", "") or ""
                        tool_name = raw_name if (raw_name and raw_name != "None") else self._active_tools_map.get(call_id, "tool")
                        content = str(getattr(msg_obj, "content", ""))
                        if self._messages is not None:
                            self._messages.update_tool_result(call_id=call_id, result=content, name=tool_name)
                        if self._app:
                            self._app.post_message(
                                self.ToolCallCompleted(call_id, content, ToolLifecycleState.SUCCESS)
                            )

                elif mode == "updates" and isinstance(data, dict):
                    if self._app:
                        from dcoder.commands.power.goal import get_goal_state, GoalHandler
                        goal_state = get_goal_state(self._app)
                        for node_name, node_update in data.items():
                            if isinstance(node_update, dict):
                                new_status = node_update.get("_goal_status")
                                new_note = node_update.get("_goal_status_note")
                                pending_comp = node_update.get("_pending_goal_completion_note")
                                updated = False
                                if new_status:
                                    goal_state.status = new_status
                                    updated = True
                                if new_note:
                                    goal_state.status_note = new_note
                                    updated = True
                                if pending_comp:
                                    goal_state.status_note = pending_comp
                                    updated = True
                                if updated:
                                    GoalHandler._sync_status_rubric(self._app, goal_state)

                    interrupts = data.get("__interrupt__", [])
                    if interrupts:
                        for intr in interrupts:
                            call_id = getattr(intr, "id", "") or "call_1"
                            tool_name = "action"
                            if self._app:
                                self._app.post_message(self.InterruptRaised(tool_name, call_id, {}))
                            approved = await self._await_approval(call_id)
                            logger.debug("TUI: approval response for %s: %s", call_id, approved)

            logger.debug("TUI: stream loop complete, finishing assistant message")
            if self._messages is not None:
                self._messages.finish_assistant_message()

            self._stats.request_count += 1
            if self._status_bar is not None:
                self._status_bar.update_stats(self._stats)
            if self._app:
                self._app.post_message(self.StreamFinished(self._stats))

        except asyncio.CancelledError:
            logger.debug("TUI: stream_turn CancelledError")
            if self._messages is not None:
                self._messages.finish_assistant_message()
            raise
        except Exception as e:
            logger.exception("TUI: stream_turn Exception: %s", e)
            if self._messages is not None:
                self._messages.finish_assistant_message()
            if self._app:
                self._app.post_message(self.StreamError(str(e)))
            raise

        finally:
            self._stats.elapsed_seconds += time.time() - start_t
            if self._status_bar is not None:
                self._status_bar.set_status("Ready")
            if self._set_spinner:
                try:
                    await self._set_spinner(None)
                except Exception:
                    pass
            logger.debug("TUI: stream_turn finally complete")


    def cancel(self) -> None:
        """Cancel the current streaming turn."""
        self._cancel_event.set()

    def submit_approval(self, call_id: str, approved: bool) -> None:
        """Submit HITL approval response from UI thread."""
        self._approval_responses[call_id] = approved
        event = self._approval_events.get(call_id)
        if event:
            event.set()

    # ── Event Routing ───────────────────────────────────

    async def _route_event(self, chunk: Any, thread_id: str) -> None:
        """Route a single stream chunk to event handlers."""
        event_type = chunk.event
        data = chunk.data

        if event_type == "messages/partial":
            for msg in data if isinstance(data, list) else [data]:
                if msg.get("type") == "ai" and msg.get("content"):
                    text = _extract_text(msg["content"])
                    if text:
                        self._stats.output_tokens += max(1, len(text) // 4)
                        if self._status_bar is not None:
                            self._status_bar.update_stats(self._stats)
                        if self._messages is not None:
                            self._messages.append_assistant_token(text)
                        if self._app:
                            self._app.post_message(self.TokenStreamed(text))

        elif event_type == "messages/complete":
            for msg in data if isinstance(data, list) else [data]:
                msg_type = msg.get("type")

                usage_meta = msg.get("usage_metadata") or msg.get("response_metadata", {}).get("usage") or msg.get("response_metadata", {}).get("token_usage")
                if isinstance(usage_meta, dict):
                    inp = usage_meta.get("input_tokens") or usage_meta.get("prompt_tokens") or 0
                    out = usage_meta.get("output_tokens") or usage_meta.get("completion_tokens") or 0
                    if inp > 0:
                        self._stats.input_tokens = max(self._stats.input_tokens, inp)
                    if out > 0:
                        self._stats.output_tokens = max(self._stats.output_tokens, out)
                    if self._status_bar is not None:
                        self._status_bar.update_stats(self._stats)

                if msg_type == "ai":
                    tool_calls = msg.get("tool_calls", [])
                    for tc in tool_calls:
                        call_id = tc.get("id", "")
                        name = tc.get("name", "unknown")
                        args = tc.get("args", {})

                        self._stats.tool_calls += 1
                        tool_state = ToolState(
                            call_id=call_id,
                            name=name,
                            args=args,
                            state=ToolLifecycleState.RUNNING,
                        )
                        self._active_tools[call_id] = tool_state

                        if self._messages is not None:
                            self._messages.add_tool_call(
                                name=name,
                                call_id=call_id,
                                args=args,
                            )
                        if self._app:
                            self._app.post_message(
                                self.ToolCallStarted(name, call_id, args)
                            )

                elif msg_type == "tool":
                    call_id = msg.get("tool_call_id", "")
                    content = msg.get("content", "")
                    status = (
                        ToolLifecycleState.ERROR
                        if msg.get("status") == "error"
                        else ToolLifecycleState.SUCCESS
                    )

                    if call_id in self._active_tools:
                        self._active_tools[call_id].state = status
                        self._active_tools[call_id].result = content

                    if self._messages is not None:
                        self._messages.update_tool_result(
                            call_id=call_id,
                            result=content,
                        )
                    if self._app:
                        self._app.post_message(
                            self.ToolCallCompleted(call_id, content, status)
                        )

        elif event_type == "__interrupt__":
            # HITL Interrupt raised
            interrupts = data if isinstance(data, list) else [data]
            for intr in interrupts:
                call_id = intr.get("id", "")
                tool_name = intr.get("tool", "unknown")
                args = intr.get("args", {})

                if self._app:
                    self._app.post_message(
                        self.InterruptRaised(tool_name, call_id, args)
                    )

                # Wait for approval response
                approved = await self._await_approval(call_id)
                logger.debug(
                    "TUI: approval response for %s: %s", call_id, approved
                )

        elif event_type == "events":
            if isinstance(data, dict):
                usage = data.get("usage", {})
                if usage:
                    self._stats.input_tokens += usage.get("prompt_tokens", 0)
                    self._stats.output_tokens += usage.get("completion_tokens", 0)
                model = data.get("model")
                if model:
                    self._stats.model = model

                # Subagent routing
                subagent = data.get("subagent")
                if subagent:
                    agent_name = subagent.get("name", "subagent")
                    token = subagent.get("token", "")
                    task = subagent.get("task", "")
                    action = subagent.get("action", "update")

                    if action == "spawn" and self._app:
                        self._app.post_message(
                            self.SubagentSpawned(agent_name, task)
                        )
                    elif action == "update" and self._app:
                        self._app.post_message(
                            self.SubagentUpdate(agent_name, token)
                        )

        elif event_type == "error":
            err_msg = data.get("message") or data.get("error") or "Unknown error"
            if self._messages is not None:
                self._messages.add_error_message(f"Server Error: {err_msg}")
            if self._app:
                self._app.post_message(self.StreamError(err_msg))

    async def _await_approval(self, call_id: str) -> bool:
        """Pause stream loop until approval event resolves."""
        evt = asyncio.Event()
        self._approval_events[call_id] = evt
        await evt.wait()
        return self._approval_responses.pop(call_id, False)
