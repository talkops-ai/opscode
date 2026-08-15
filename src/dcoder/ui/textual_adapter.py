"""Stream bridge between LangGraph SDK client and Textual widgets.

The ``TextualAdapter`` consumes streaming events from ``client.runs.stream()``
and routes them directly to Textual widgets via widget mutation.  Only
lifecycle events (interrupts, subagents, stream end/error) use the Textual
message bus.  High-frequency token and tool updates bypass ``post_message``
to avoid flooding the event queue.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import math
import time

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from textual.message import Message

from dcoder.utils.session_stats import SessionStats
from dcoder.ui._tool_stream import (
    ToolCallBuffer,
    ToolCallBufferKey,
    tool_call_buffer_key,
    count_unemitted_tool_calls,
)

from dcoder.config.settings import get_glyphs

if TYPE_CHECKING:
    from dcoder.ui.messages import MessageList
    from dcoder.ui.status import StatusBar

logger = logging.getLogger(__name__)


def _read_mentioned_file(file_path: Path, max_embed_bytes: int = 256 * 1024) -> str:
    """Read a mentioned file for inline embedding."""
    file_size = file_path.stat().st_size
    if file_size > max_embed_bytes:
        size_kb = file_size // 1024
        return (
            f"\n### {file_path.name}\n"
            f"Path: `{file_path}`\n"
            f"Size: {size_kb}KB (too large to embed, use read_file tool to view)"
        )
    content = file_path.read_text(encoding="utf-8")
    return f"\n### {file_path.name}\nPath: `{file_path}`\n```text\n{content}\n```"


def _is_renderable_subagent_event(data: Any, *, is_main_agent: bool) -> bool:
    return is_main_agent and isinstance(data, dict) and data.get("type") == "subagent"


def _format_rubric_event(data: dict[str, Any]) -> str | None:
    """Format a concise rubric custom-stream event for the transcript."""
    glyphs = get_glyphs()
    event_type = data.get("type")
    if event_type == "rubric_evaluation_start":
        iteration = data.get("iteration", 0)
        show_iteration = data.get("show_iteration") is True
        label = (
            f" (iteration {iteration + 1})"
            if show_iteration and isinstance(iteration, int)
            else ""
        )
        return f"{glyphs.hourglass} Checking acceptance criteria{label}{glyphs.ellipsis}"
    if event_type != "rubric_evaluation_end":
        return None

    result = data.get("result")
    if result is None:
        return None
    if result == "satisfied":
        return f"{glyphs.checkmark} Acceptance criteria satisfied"
    if result == "needs_revision":
        return f"{glyphs.retry} Acceptance criteria not yet satisfied"
    if result == "max_iterations_reached":
        return f"{glyphs.warning} Acceptance criteria not yet satisfied (iteration limit reached)"
    if result == "failed":
        return f"{glyphs.warning} Rubric is invalid or cannot be evaluated"
    if result == "grader_error":
        return f"{glyphs.warning} Acceptance criteria check failed"
    return f"{glyphs.warning} Acceptance criteria check ended"


def _format_rubric_details(data: dict[str, Any], *, goal_active: bool = False) -> str:
    """Format complete grader details without serializing or truncating payloads."""
    result = data.get("result")
    if result in {None, "satisfied"}:
        return ""

    sections: list[str] = []
    explanation = str(data.get("explanation") or "").strip()
    if explanation:
        sections.append(f"Explanation\n{explanation}")

    criteria = data.get("criteria")
    failing: list[tuple[str, str]] = []
    if isinstance(criteria, list):
        for criterion in criteria:
            if isinstance(criterion, dict) and criterion.get("passed") is False:
                name = str(criterion.get("name") or "Unnamed criterion").strip()
                gap = str(criterion.get("gap") or "").strip()
                failing.append((name, gap))
    if failing:
        lines = ["Unmet criteria"]
        for name, gap in failing:
            lines.append(f"- {name}" + (f"\n  {gap}" if gap else ""))
        sections.append("\n".join(lines))

    if result == "max_iterations_reached" and goal_active:
        next_step = (
            "The goal remains active. Continue with another prompt to resume or "
            "retry, use `/goal <objective>` to amend it, or `/goal clear` to clear it."
        )
    elif result in {"needs_revision", "max_iterations_reached"}:
        next_step = "Address every unmet criterion, then retry the check."
    elif result == "failed":
        next_step = "Review or replace the rubric before grading again."
    elif result == "grader_error":
        next_step = "Retry the check, or choose a different grader model."
    else:
        next_step = "Review the grader details before continuing."
    sections.append(f"Next step\n{next_step}")
    return "\n\n".join(sections)


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






class TextualAdapter:
    """Bridge between LangGraph SDK stream events and Textual widgets.

    Parses the event stream from ``client.runs.stream()`` and posts custom
    Textual events for thread-safe UI rendering and lifecycle tracking.
    """

    # ── Custom Textual Events ────────────────────────────
    # Only events that require app-level handling (lifecycle, approvals,
    # subagents) use the Textual message bus.  High-frequency token and
    # tool-call updates bypass post_message entirely and mutate widgets
    # directly from the stream loop — matching the reference dcode pattern
    # — to avoid flooding the event queue.

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
        def __init__(self, agent_name: str, token: str, status: str = "") -> None:
            super().__init__()
            self.agent_name = agent_name
            self.token = token
            self.status = status

    class TokenStreamed(Message):
        """Fired when a new content token is streamed from the model."""
        def __init__(self, token: str) -> None:
            super().__init__()
            self.token = token

    class ToolCallStarted(Message):
        """Fired when a tool call begins execution."""
        def __init__(self, name: str, call_id: str = "") -> None:
            super().__init__()
            self.name = name
            self.call_id = call_id

    class ToolCallCompleted(Message):
        """Fired when a tool call finishes."""
        def __init__(self, name: str, call_id: str = "", result: str = "") -> None:
            super().__init__()
            self.name = name
            self.call_id = call_id
            self.result = result

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
        on_subagent_event: Callable[[dict[str, Any]], None] | None = None,
        app: Any = None,
        prompt_manager: Any = None,
        request_approval: Callable[..., Any] | None = None,
    ) -> None:
        self._client = client
        self._assistant_id = assistant_id
        self._messages: MessageList | None = messages_widget
        self._status_bar: StatusBar | None = status_bar
        self._auto_approve = auto_approve
        self._set_spinner = set_spinner
        self._on_subagent_event = on_subagent_event
        self._app = app
        self._prompt_manager = prompt_manager
        self._request_approval = request_approval
        self._stats = SessionStats()
        self._cancel_event = asyncio.Event()
        self._active_tools_map: dict[str, str] = {}
        self._approval_events: dict[str, asyncio.Event] = {}
        self._approval_responses: dict[str, bool] = {}
        self._turn_number = 0

    @property
    def _effective_request_approval(self) -> Callable[..., Any] | None:
        if self._request_approval is not None:
            return self._request_approval
        if self._app and hasattr(self._app, "_request_approval"):
            return self._app._request_approval
        return None

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
        graph_input: dict[str, Any] | None = None,
    ) -> None:
        """Run one agent turn, routing stream events to Textual widgets."""
        import uuid
        from langchain_core.messages import AIMessageChunk, HumanMessage, ToolMessage
        from dcoder.middleware.auto_mode import USER_PROMPT_METADATA_KEY, user_prompt_metadata

        turn_id: str | None = None

        if graph_input is not None:
            input_msg: dict[str, Any] = graph_input
        else:
            from dcoder.input import parse_file_mentions

            prompt_text, mentioned_files = parse_file_mentions(prompt)
            max_embed_bytes = 256 * 1024

            if mentioned_files:
                context_parts = [prompt_text, "\n\n## Referenced Files\n"]
                for file_path in mentioned_files:
                    try:
                        part = _read_mentioned_file(file_path, max_embed_bytes)
                        context_parts.append(part)
                    except Exception as e:
                        context_parts.append(f"\n### {file_path.name}\n[Error reading file: {e}]")
                final_content = "\n".join(context_parts)
            else:
                final_content = prompt_text

            self._turn_number += 1
            turn_id = str(uuid.uuid4())

            human_msg = HumanMessage(
                content=final_content,
                additional_kwargs={
                    USER_PROMPT_METADATA_KEY: user_prompt_metadata(
                        literal_user_text=prompt,
                        referenced_paths=[str(p) for p in mentioned_files],
                        turn_id=turn_id,
                    )
                },
            )
            input_msg = {
                "messages": [human_msg],
                "goal_criteria_request": None,
            }

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
                    input_msg["rubric"] = goal_state.rubric

        from dcoder.approval_mode import ApprovalMode, approval_mode_key, awrite_approval_mode, coerce_approval_mode
        from dcoder.config.metadata import build_stream_config

        raw_mode = getattr(self._app, "_approval_mode", ApprovalMode.MANUAL) if self._app is not None else ApprovalMode.MANUAL
        selected_mode = raw_mode if isinstance(raw_mode, ApprovalMode) else coerce_approval_mode(raw_mode)

        agent_obj = (
            self._client
            or (getattr(self._app, "_client", None) if self._app is not None else None)
            or (getattr(self._app, "_agent", None) if self._app is not None else None)
        )
        live_key: str | None = None
        if agent_obj is not None:
            try:
                live_key = await awrite_approval_mode(agent_obj, thread_id, mode=selected_mode)
            except Exception:
                logger.warning("Failed to persist approval mode to store", exc_info=True)

        auto_approve_active = (selected_mode is ApprovalMode.YOLO)

        eff = None
        if self._app is not None:
            eff = getattr(self._app, "_reasoning_effort", None) or getattr(
                getattr(self._app, "settings", None), "reasoning_effort", None
            )

        config = await asyncio.to_thread(
            build_stream_config,
            thread_id,
            getattr(self, "_assistant_id", "agent"),
            turn_id=turn_id,
            turn_number=self._turn_number,
            approval_mode=selected_mode.value,
            approval_mode_key=live_key,
            auto_approve=auto_approve_active,
            reasoning_effort=eff or "medium",
        )
        if context is None or not isinstance(context, dict):
            context = {}
        context["thread_id"] = thread_id
        if turn_id is not None:
            context["turn_id"] = turn_id

        context["approval_mode"] = selected_mode.value
        context["auto_approve"] = (selected_mode is ApprovalMode.YOLO)
        if live_key is not None:
            context["approval_mode_key"] = live_key
        else:
            context.pop("approval_mode_key", None)

        logger.debug("TUI: stream_turn start, thread_id: %s, context: %s", thread_id, context)

        start_t = time.time()
        self._stats.input_tokens += max(1, len(prompt) // 4)
        if self._status_bar is not None:
            total_tokens = self._stats.input_tokens + self._stats.output_tokens
            self._status_bar.set_tokens(total_tokens)

        thinking_start_t: float | None = None


        first_token_received = False
        turn_context_tokens = 0

        try:
            stream_input: Any = input_msg
            
            # Map tracking active assistant messages and pending text by namespace
            assistant_message_by_namespace: dict[tuple, Any] = {}
            pending_text_by_namespace: dict[tuple, str] = {}
            
            # Buffers for tool call streaming
            tool_call_buffers: dict[ToolCallBufferKey, ToolCallBuffer] = {}
            displayed_tool_ids: set[str] = set()

            while True:
                logger.debug("TUI: calling agent.astream...")

                interrupt_occurred = False
                resume_payload: dict[str, Any] = {}
                pending_interrupts: dict[str, Any] = {}

                # Show the Thinking spinner before each astream iteration
                if self._set_spinner and not getattr(self, "_current_tool_messages", {}):
                    await self._set_spinner("Thinking")

                async for chunk in self._client.astream(
                    stream_input,
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

                    namespace, current_stream_mode, data = chunk
                    ns_key = tuple(namespace) if namespace else ()
                    is_main_agent = ns_key == ()

                    if current_stream_mode == "custom":
                        if isinstance(data, dict) and data.get("type") == "session_cost":
                            total_usd = data.get("total")
                            if isinstance(total_usd, (int, float)) and math.isfinite(total_usd) and total_usd >= 0:
                                cost_val = float(total_usd)
                                self._stats.total_cost_usd = cost_val
                                if self._app:
                                    setattr(self._app, "_session_cost_usd", cost_val)
                                if self._status_bar is not None:
                                    self._status_bar.set_cost(cost_val)
                            continue

                        if (
                            self._on_subagent_event is not None
                            and _is_renderable_subagent_event(data, is_main_agent=is_main_agent)
                        ):
                            try:
                                self._on_subagent_event(data)
                            except Exception:
                                logger.exception("subagent panel event handler failed")
                        elif isinstance(data, dict):
                            rubric_msg = data
                            formatted_event = _format_rubric_event(rubric_msg)
                            if formatted_event is not None and is_main_agent and self._messages is not None:
                                details = (
                                    _format_rubric_details(rubric_msg, goal_active=True)
                                    if rubric_msg.get("type") == "rubric_evaluation_end"
                                    else ""
                                )
                                from dcoder.ui.messages import RubricResultMessage, SystemMessage, ErrorMessage
                                if rubric_msg.get("type") == "rubric_evaluation_end":
                                    if self._app is not None and hasattr(self._app, "_handle_rubric_evaluation_end"):
                                        try:
                                            self._app._handle_rubric_evaluation_end(rubric_msg)
                                        except Exception:
                                            pass
                                    if rubric_msg.get("result") == "grader_error":
                                        widget = ErrorMessage(
                                            "Acceptance-criteria grading failed because of a grader or "
                                            "infrastructure error. The goal remains active, and its "
                                            "completion request is still pending; it will be re-graded on "
                                            "your next turn."
                                        )
                                    elif details:
                                        widget = RubricResultMessage(formatted_event, details)
                                    else:
                                        widget = SystemMessage(formatted_event)
                                else:
                                    widget = SystemMessage(formatted_event)
                                self._messages.mount(widget)
                        continue

                    elif current_stream_mode == "updates":
                        if not isinstance(data, dict):
                            continue
                        interrupts = data.get("__interrupt__")
                        if interrupts:
                            interrupt_occurred = True
                            for interrupt_obj in interrupts:
                                interrupt_id = getattr(interrupt_obj, "id", None)
                                interrupt_val = getattr(interrupt_obj, "value", None)
                                
                                if interrupt_val and interrupt_id:
                                    logger.debug("TUI: Handle interrupt %s: %s", interrupt_id, interrupt_val)
                                    pending_interrupts[interrupt_id] = interrupt_val
                                    
                    elif current_stream_mode == "messages":
                        msg_obj, meta = data if isinstance(data, tuple) else (data, {})
                        
                        # Handle usage stats
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
                                turn_context_tokens = context_toks
                                prior_tokens = getattr(self._app, "_cumulative_session_tokens", 0) if self._app else 0
                                total_tokens = prior_tokens + context_toks
                                if self._app:
                                    setattr(self._app, "_context_tokens", total_tokens)
                                if self._status_bar is not None:
                                    self._status_bar.set_tokens(total_tokens)

                        if msg_obj.__class__.__name__ == "ToolMessage":
                            call_id = getattr(msg_obj, "tool_call_id", "") or ""
                            raw_name = getattr(msg_obj, "name", "") or ""
                            tool_name = raw_name if (raw_name and raw_name != "None") else self._active_tools_map.get(call_id, "tool")
                            content = str(getattr(msg_obj, "content", ""))
                            if self._messages is not None and is_main_agent:
                                self._messages.update_tool_result(call_id=call_id, result=content, name=tool_name)
                            if self._set_spinner:
                                try:
                                    await self._set_spinner("Thinking")
                                except Exception:
                                    pass

                        # Process AIMessageChunk blocks
                        elif hasattr(msg_obj, "content_blocks"):
                            blocks = msg_obj.content_blocks
                            for block in blocks:
                                block_type = block.get("type")

                                if block_type == "text":
                                    text = block.get("text", "")
                                    if text:
                                        pending_text = pending_text_by_namespace.get(ns_key, "")
                                        pending_text += text
                                        pending_text_by_namespace[ns_key] = pending_text
                                        if ns_key not in assistant_message_by_namespace:
                                            assistant_message_by_namespace[ns_key] = True
                                            if self._set_spinner:
                                                await self._set_spinner("Thinking")

                                        if self._messages is not None and is_main_agent:
                                            self._messages.append_assistant_token(text)

                                elif block_type in {"tool_call_chunk", "tool_call"}:
                                    chunk_name = block.get("name")
                                    chunk_args = block.get("args")
                                    chunk_id = block.get("id")
                                    chunk_index = block.get("index")

                                    buffer_key = tool_call_buffer_key(chunk_index, chunk_id, len(tool_call_buffers))
                                    buffer = tool_call_buffers.setdefault(buffer_key, ToolCallBuffer())
                                    buffer.ingest(name=chunk_name, tool_id=chunk_id, args=chunk_args)

                                    buffer_name = buffer.name
                                    buffer_id = buffer.tool_id
                                    if buffer_name is None:
                                        continue

                                    parsed_args = buffer.parse_args()
                                    if parsed_args is None:
                                        continue

                                    if self._messages is not None and is_main_agent:
                                        self._messages.finish_assistant_message()
                                    pending_text_by_namespace.pop(ns_key, None)
                                    assistant_message_by_namespace.pop(ns_key, None)

                                    if buffer_id is not None and buffer_id not in displayed_tool_ids:
                                        displayed_tool_ids.add(buffer_id)
                                        if self._set_spinner:
                                            await self._set_spinner("Thinking")

                                        if self._messages is not None and is_main_agent:
                                            self._messages.add_tool_call(name=buffer_name, call_id=buffer_id, args=parsed_args)
                                            self._active_tools_map[buffer_id] = buffer_name

                if self._cancel_event.is_set():
                    break

                logger.debug("TUI: stream loop complete, finishing assistant message and regrouping tools")
                if self._messages is not None:
                    self._messages.finish_assistant_message()
                    regroup_fn = getattr(self._messages, "regroup_completed_tools", None)
                    if callable(regroup_fn):
                        res = regroup_fn()
                        if inspect.isawaitable(res):
                            await res
                    
                if pending_interrupts:
                    req_approval_fn = self._effective_request_approval
                    for int_id, int_val in list(pending_interrupts.items()):
                        action_requests = int_val.get("action_requests", []) if isinstance(int_val, dict) else []

                        if self._auto_approve:
                            decisions = [{"type": "approve"} for _ in action_requests]
                            resume_payload[int_id] = {"decisions": decisions}
                            continue

                        if req_approval_fn is not None:
                            future = await req_approval_fn(
                                action_requests, self._assistant_id
                            )
                            decision = await future

                            if (
                                isinstance(decision, dict)
                                and decision.get("type") == "auto_approve_all"
                                and getattr(self._app, "_on_auto_approve_enabled", None) is not None
                            ):
                                callback_result = self._app._on_auto_approve_enabled()
                                enabled = (
                                    await callback_result
                                    if inspect.isawaitable(callback_result)
                                    else callback_result
                                )
                                if enabled is None:
                                    enabled = True
                                if enabled is False:
                                    continue

                            if isinstance(decision, dict):
                                decision_type = decision.get("type")
                                if decision_type in {"approve", "auto_approve_all"}:
                                    decisions = [{"type": "approve"} for _ in action_requests]
                                elif decision_type == "switch_manual":
                                    decisions = [{"type": "reject"} for _ in action_requests]
                                elif decision_type == "reject":
                                    reject_msg = decision.get("message")
                                    rej_dict: dict[str, Any] = {"type": "reject"}
                                    if reject_msg:
                                        rej_dict["message"] = reject_msg
                                    decisions = [rej_dict for _ in action_requests]
                                else:
                                    decisions = [{"type": "approve"} for _ in action_requests]
                            else:
                                decisions = [{"type": "approve"} for _ in action_requests]
                            resume_payload[int_id] = {"decisions": decisions}
                        else:
                            # Backwards-compatible fallback
                            call_ids = [f"{int_id}_{i}" for i in range(len(action_requests))]
                            for i, req in enumerate(action_requests):
                                if self._app:
                                    self._app.post_message(
                                        self.InterruptRaised(
                                            tool_name=req.get("action") or req.get("name", "unknown"),
                                            call_id=call_ids[i],
                                            args=req.get("args", {})
                                        )
                                    )
                            if call_ids:
                                approved_results = await asyncio.gather(*(self._await_approval(cid) for cid in call_ids))
                                decisions = [{"type": "approve" if approved else "reject"} for approved in approved_results]
                            else:
                                decisions = []
                            resume_payload[int_id] = {"decisions": decisions}

                    from langgraph.types import Command
                    stream_input = Command(resume=resume_payload)
                    continue
                else:
                    break

            self._stats.request_count += 1
            if self._status_bar is not None:
                total_tokens = self._stats.input_tokens + self._stats.output_tokens
                self._status_bar.set_tokens(total_tokens)
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
                from dcoder.ui.messages import ErrorMessage
                self._messages.mount(ErrorMessage(f"Agent execution failed: {e}"))
            if self._app:
                self._app.post_message(self.StreamError(str(e)))
            raise

        finally:
            self._stats.wall_time_seconds += time.time() - start_t
            if self._app and turn_context_tokens > 0:
                prior = getattr(self._app, "_cumulative_session_tokens", 0)
                setattr(self._app, "_cumulative_session_tokens", prior + turn_context_tokens)
            # Dismiss the spinner and clear the status bar on turn end.
            if self._set_spinner:
                try:
                    await self._set_spinner(None)
                except Exception:
                    pass
            if self._status_bar is not None:
                self._status_bar.set_status("")
            logger.debug("TUI: stream_turn finally complete")


    def cancel(self) -> None:
        """Cancel the current streaming turn."""
        self._cancel_event.set()

    def submit_approval(self, call_id: str, approved: bool) -> None:
        """Submit HITL approval response from UI thread."""
        self._approval_responses[call_id] = approved
        event = self._approval_events.setdefault(call_id, asyncio.Event())
        event.set()

    async def _await_approval(self, call_id: str) -> bool:
        """Pause stream loop until approval event resolves."""
        if call_id in self._approval_responses:
            return self._approval_responses.pop(call_id)
        evt = self._approval_events.setdefault(call_id, asyncio.Event())
        await evt.wait()
        self._approval_events.pop(call_id, None)
        return self._approval_responses.pop(call_id, False)
