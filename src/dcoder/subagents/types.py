"""Type definitions for subagent metadata."""

from typing import NotRequired, TypedDict

class SubagentMetadata(TypedDict):
    """Metadata for a custom subagent loaded from filesystem."""
    name: str
    description: str
    system_prompt: str
    model: NotRequired[str | None]
    source: str
    path: str

