"""Remote agent client — wrapper around LangGraph's RemoteGraph (replicated from reference/deepagents_code).

Delegates streaming, state management, and SSE handling to
langgraph.pregel.remote.RemoteGraph. Converts streamed message dicts into
LangChain message objects for TextualAdapter.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

logger = logging.getLogger(__name__)

_RUN_CANCEL_WAIT_SECONDS = 10.0


def _require_thread_id(config: Mapping[str, Any] | None) -> str:
    thread_id = (config or {}).get("configurable", {}).get("thread_id")
    if not thread_id:
        msg = "thread_id is required in config.configurable"
        raise ValueError(msg)
    return thread_id


def agent_error_type(exc: BaseException) -> str:
    payload = exc.args[0] if exc.args else None
    if isinstance(payload, dict):
        err_type = payload.get("error")
        if isinstance(err_type, str) and err_type:
            return err_type
    return type(exc).__name__


def format_agent_exception(exc: BaseException) -> str:
    payload = exc.args[0] if exc.args else None
    if isinstance(payload, dict):
        err_type = agent_error_type(exc)
        message = payload.get("message")
        if isinstance(message, str) and message:
            return f"{err_type}: {message}"
        return err_type
    text = str(exc)
    return text or type(exc).__name__

_KNOWN_STREAM_MODES = {"messages", "updates", "custom", "values", "debug"}


def _parse_stream_item(raw_item: Any) -> tuple[tuple[str, ...], str, Any] | None:
    """Parse a stream chunk into (namespace, mode, data) regardless of tuple packing order."""
    if not isinstance(raw_item, tuple):
        return None
    if len(raw_item) == 2:
        first, second = raw_item
        if isinstance(first, str) and first in _KNOWN_STREAM_MODES:
            return (), first, second
        if isinstance(second, str) and second in _KNOWN_STREAM_MODES:
            return (), second, first
        return (), str(first), second
    if len(raw_item) == 3:
        first, second, third = raw_item
        if isinstance(first, str) and first in _KNOWN_STREAM_MODES:
            return (), first, second
        if isinstance(second, str) and second in _KNOWN_STREAM_MODES:
            ns = tuple(first) if isinstance(first, (list, tuple)) else ()
            return ns, second, third
        if isinstance(third, str) and third in _KNOWN_STREAM_MODES:
            ns = tuple(first) if isinstance(first, (list, tuple)) else ()
            return ns, third, second
        ns = tuple(first) if isinstance(first, (list, tuple)) else ()
        return ns, str(second) if isinstance(second, str) else "updates", third
    return None


class RemoteAgent:
    """Client that talks to a LangGraph server over HTTP+SSE."""

    def __init__(
        self,
        url: str,
        *,
        graph_name: str = "agent",
        api_key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._url = url
        self._graph_name = graph_name
        self._api_key = api_key
        self._headers = headers
        self._graph: Any = None

    def _get_graph(self) -> Any:
        if self._graph is None:
            from langgraph.pregel.remote import RemoteGraph

            self._graph = RemoteGraph(
                self._graph_name,
                url=self._url,
                api_key=self._api_key,
                headers=self._headers,
            )
        return self._graph

    async def astream(
        self,
        input: dict | Any,
        *,
        stream_mode: list[str] | None = None,
        subgraphs: bool = False,
        config: dict[str, Any] | None = None,
        context: Any | None = None,
        durability: str | None = None,
    ) -> AsyncIterator[tuple[tuple[str, ...], str, Any]]:
        from langchain_core.messages import BaseMessage

        _require_thread_id(config)

        graph = self._get_graph()
        config = _prepare_config(config)
        dropped_count = 0

        async for raw_item in graph.astream(
            input,
            stream_mode=stream_mode or ["messages", "updates"],
            subgraphs=subgraphs,
            config=config,
            context=context,
        ):
            parsed = _parse_stream_item(raw_item)
            if parsed is None:
                continue
            ns, mode, data = parsed

            logger.debug("RemoteGraph event ns=%s mode=%s data_type=%s", ns, mode, type(data).__name__)

            if mode == "messages":
                msg_dict, meta = data if isinstance(data, tuple) else (data, {})
                if isinstance(msg_dict, dict):
                    msg_obj = _convert_message_data(msg_dict)
                    if msg_obj is not None:
                        yield (ns, "messages", (msg_obj, meta or {}))
                    else:
                        dropped_count += 1
                elif isinstance(msg_dict, BaseMessage):
                    yield (ns, "messages", (msg_dict, meta or {}))
                else:
                    logger.warning("Unexpected message data type in stream: %s", type(msg_dict).__name__)
                continue

            if mode == "updates" and isinstance(data, dict):
                update_data = data
                if "__interrupt__" in data:
                    update_data = {
                        **data,
                        "__interrupt__": _convert_interrupts(data["__interrupt__"]),
                    }
                yield (ns, "updates", update_data)
                continue

            yield (ns, mode, data)

        if dropped_count:
            logger.warning("Dropped %d message(s) during stream due to conversion failures", dropped_count)

    async def aget_state(self, config: dict[str, Any]) -> Any:
        from langgraph_sdk.errors import NotFoundError

        thread_id = _require_thread_id(config)
        graph = self._get_graph()
        try:
            return await graph.aget_state(_prepare_config(config))
        except NotFoundError:
            logger.debug("Thread %s not found on server", thread_id)
            return None
        except TypeError as e:
            if "subscriptable" in str(e).lower():
                logger.debug("Thread %s has no checkpoint yet", thread_id)
                return None
            raise

    async def create_thread(self) -> dict[str, Any]:
        """Create thread using SDK client."""
        client = self._get_graph()._validate_client()
        return await client.threads.create()


def _prepare_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    config = dict(config or {})
    configurable = dict(config.get("configurable", {}))
    config["configurable"] = configurable
    return config


def _convert_interrupts(raw: Any) -> list[Any]:
    from langgraph.types import Interrupt

    if not isinstance(raw, list):
        return [raw] if raw is not None else []
    results = []
    for item in raw:
        if isinstance(item, Interrupt):
            results.append(item)
        elif isinstance(item, dict) and "value" in item:
            results.append(Interrupt(value=item["value"], id=item.get("id", "")))
        else:
            results.append(item)
    return results


def _convert_ai_message(data: dict[str, Any]) -> Any:
    from langchain_core.messages import AIMessageChunk

    content = data.get("content", "")
    tool_call_chunks = data.get("tool_call_chunks", [])
    tool_calls = data.get("tool_calls", [])
    usage_metadata = data.get("usage_metadata")
    response_metadata = data.get("response_metadata", {})

    kwargs: dict[str, Any] = {
        "content": content,
        "id": data.get("id"),
        "response_metadata": response_metadata,
    }

    if tool_call_chunks:
        kwargs["tool_call_chunks"] = [
            {
                "name": tc.get("name"),
                "args": tc.get("args", ""),
                "id": tc.get("id"),
                "index": tc.get("index", i),
            }
            for i, tc in enumerate(tool_call_chunks)
        ]
    elif tool_calls:
        has_str_args = any(isinstance(tc.get("args"), str) for tc in tool_calls)
        if has_str_args:
            kwargs["tool_call_chunks"] = [
                {
                    "name": tc.get("name"),
                    "args": tc.get("args", ""),
                    "id": tc.get("id"),
                    "index": i,
                }
                for i, tc in enumerate(tool_calls)
            ]
        else:
            kwargs["tool_calls"] = tool_calls

    try:
        chunk = AIMessageChunk(**kwargs)
    except (TypeError, ValueError, KeyError):
        logger.warning(
            "Failed to construct AIMessageChunk from server data (id=%s)",
            data.get("id"),
            exc_info=True,
        )
        return None

    if usage_metadata:
        chunk.usage_metadata = usage_metadata
    return chunk


def _convert_human_message(data: dict[str, Any]) -> Any:
    from langchain_core.messages import HumanMessage

    content = data.get("content", "")
    try:
        return HumanMessage(content=content, id=data.get("id"))
    except Exception:
        return None


def _convert_tool_message(data: dict[str, Any]) -> Any:
    from langchain_core.messages import ToolMessage

    content = data.get("content", "")
    tool_call_id = data.get("tool_call_id", "")
    try:
        return ToolMessage(
            content=content,
            tool_call_id=tool_call_id,
            name=data.get("name", ""),
            id=data.get("id"),
            status=data.get("status", "success"),
        )
    except Exception:
        return None


_MESSAGE_CONVERTERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "ai": _convert_ai_message,
    "AIMessage": _convert_ai_message,
    "AIMessageChunk": _convert_ai_message,
    "human": _convert_human_message,
    "HumanMessage": _convert_human_message,
    "tool": _convert_tool_message,
    "ToolMessage": _convert_tool_message,
}


def _convert_message_data(data: dict[str, Any]) -> Any:
    msg_type = data.get("type", "")
    converter = _MESSAGE_CONVERTERS.get(msg_type)
    if converter is not None:
        return converter(data)
    if "content" in data:
        return _convert_ai_message(data)
    return None
