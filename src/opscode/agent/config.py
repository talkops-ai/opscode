"""Agent mode discovery and default persistence.

OpsCode's LangGraph server exposes two assistant modes:
- ``agent`` — the main DevOps coding agent (new thread, fresh conversation)
- ``conversation_history`` — browse and search past conversations

These are NOT filesystem directories — they are the graph names / assistant
IDs that the LangGraph server routes to.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from opscode.config.paths import STATE_DIR as _STATE_DIR
_DEFAULT_AGENT_FILE = _STATE_DIR / "default_agent.json"

# The two modes the LangGraph server supports
AVAILABLE_AGENTS: list[str] = [
    "agent",
    "conversation_history",
]


def get_available_agent_names() -> list[str]:
    """Return the list of available agent modes.

    Returns:
        List of agent/assistant IDs the LangGraph server supports.
    """
    return list(AVAILABLE_AGENTS)


from opscode.config.toml_config import (
    clear_default_agent as clear_default_agent,
    load_default_agent as _toml_load_default_agent,
    load_recent_agent as load_recent_agent,
    save_default_agent as save_default_agent,
    save_recent_agent as save_recent_agent,
)


def load_default_agent() -> str | None:
    """Load the persisted default agent name from config.toml or fallbacks."""
    default_agent = _toml_load_default_agent()
    if default_agent:
        return default_agent
    recent_agent = load_recent_agent()
    if recent_agent:
        return recent_agent
    try:
        if _DEFAULT_AGENT_FILE.exists():
            data = json.loads(_DEFAULT_AGENT_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "agent" in data:
                return str(data["agent"])
    except Exception:
        logger.debug("Failed to load default agent fallback", exc_info=True)
    return None

