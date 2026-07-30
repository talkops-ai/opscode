"""Subagent loading and delegation catalog for dcoder."""

from dcoder.subagents.types import SubagentMetadata
from dcoder.subagents.loader import list_subagents
from dcoder.subagents.devops_subagents import get_built_in_subagents

__all__ = [
    "SubagentMetadata",
    "list_subagents",
    "get_built_in_subagents",
]
