"""Lightweight shared constants for the opscode app.

This module is intentionally dependency-free (no third-party imports, no
sibling-module imports) so any other module — including the startup-critical
``main.py`` and the heavy ``agent.py`` — can import from it without triggering a
chain of expensive imports.
"""

from __future__ import annotations

from typing import Final

DEFAULT_AGENT_NAME: Final[str] = "agent"
"""Default agent / assistant identifier when no ``-a`` flag is given."""

FS_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    {"ls", "read_file", "write_file", "edit_file", "delete", "glob", "grep", "execute"}
)
"""Mirror of the SDK's ``FsToolName`` literal members.

Hardcoded here rather than derived from ``deepagents.FsToolName`` because
``deepagents`` must not be imported on the arg-parsing hot path; this module is
dependency-free and safe for ``main.py`` to import.
"""

SDK_DEFAULT_RUBRIC_MAX_ITERATIONS: Final[int] = 3
"""Default ``RubricMiddleware.max_iterations``, shown without importing the SDK.

Hardcoded rather than read from ``deepagents.middleware.rubric.RubricMiddleware``
because this module is dependency-free and importing the SDK for a display
string would violate the startup-performance rule.
"""

SYSTEM_MESSAGE_PREFIX: Final[str] = "[SYSTEM]"
"""Prefix for synthetic human messages (e.g. interrupt cancellation notices).

Such messages are written to the ``messages`` channel for the agent's benefit on
resume but are not user-authored, so they are filtered out of both the rendered
transcript and a thread's initial prompt.  Shared here so the single producer
(``textual_adapter``) and its consumers (``app``, ``sessions``) agree on one
literal.
"""
