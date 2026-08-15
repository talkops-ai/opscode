"""Runtime thread identification tool for opscode."""

from __future__ import annotations

import logging
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

logger = logging.getLogger("opscode")


@tool
def get_current_thread_id(config: RunnableConfig) -> str:
    """Get the current Deep Agents thread ID for LangSmith or MCP tooling.

    Args:
        config: Runtime config injected by LangChain.

    Returns:
        The current `configurable.thread_id`, or an explanatory message if missing.
    """
    thread_id = config.get("configurable", {}).get("thread_id")
    if isinstance(thread_id, str) and thread_id:
        return thread_id
    return "No current thread ID is available."
