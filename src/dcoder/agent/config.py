"""Agent mode discovery and default persistence.

DCoder's LangGraph server exposes two assistant modes:
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

_STATE_DIR = Path.home() / ".dcoder" / ".state"
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


def load_default_agent() -> str | None:
    """Load the persisted default agent name.

    Returns:
        Agent name string, or ``None`` if no default is saved.
    """
    try:
        if _DEFAULT_AGENT_FILE.exists():
            data = json.loads(_DEFAULT_AGENT_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "agent" in data:
                return str(data["agent"])
    except Exception:
        logger.debug("Failed to load default agent", exc_info=True)
    return None


def save_default_agent(agent_name: str) -> bool:
    """Persist the user's default agent.

    Args:
        agent_name: Agent name to save as default.

    Returns:
        ``True`` if saved successfully.
    """
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _DEFAULT_AGENT_FILE.write_text(
            json.dumps({"agent": agent_name}, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception:
        logger.debug("Failed to save default agent", exc_info=True)
        return False


def clear_default_agent() -> bool:
    """Remove the saved default agent.

    Returns:
        ``True`` if cleared successfully (or already absent).
    """
    try:
        if _DEFAULT_AGENT_FILE.exists():
            _DEFAULT_AGENT_FILE.unlink()
        return True
    except Exception:
        logger.debug("Failed to clear default agent", exc_info=True)
        return False
