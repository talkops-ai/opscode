"""Subagent loading and delegation catalog for opscode."""

from opscode.subagents.types import SubagentMetadata
from opscode.subagents.loader import list_subagents
from opscode.subagents.subagents_parser import parse_built_in_subagents, parse_subagent_bundle


def get_built_in_subagents() -> list[SubagentMetadata]:
    """Return built-in subagent metadata parsed from `src/opscode/built_in_subagents/`."""
    return parse_built_in_subagents()


__all__ = [
    "SubagentMetadata",
    "list_subagents",
    "get_built_in_subagents",
    "parse_built_in_subagents",
    "parse_subagent_bundle",
]
