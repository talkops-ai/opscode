"""Subagent loading and delegation catalog for dcoder."""

from dcoder.subagents.types import SubagentMetadata
from dcoder.subagents.loader import list_subagents
from dcoder.subagents.subagents_parser import parse_built_in_subagents, parse_subagent_bundle


def get_built_in_subagents() -> list[SubagentMetadata]:
    """Return built-in subagent metadata parsed from `src/dcoder/built_in_subagents/`."""
    return parse_built_in_subagents()


__all__ = [
    "SubagentMetadata",
    "list_subagents",
    "get_built_in_subagents",
    "parse_built_in_subagents",
    "parse_subagent_bundle",
]
