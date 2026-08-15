"""Backwards-compatibility re-exports for goal tools and middleware."""

from __future__ import annotations

from opscode.middleware.goal_tools import GoalToolsMiddleware
from opscode.tools.goal_tools import (
    GoalSnapshot,
    GoalStatus,
    RubricSnapshot,
    _goal_snapshot,
    _rubric_snapshot,
    _update_goal_command,
    get_goal,
    get_rubric,
    update_goal,
)

__all__ = [
    "GoalToolsMiddleware",
    "GoalStatus",
    "RubricSnapshot",
    "GoalSnapshot",
    "_rubric_snapshot",
    "_goal_snapshot",
    "_update_goal_command",
    "get_rubric",
    "get_goal",
    "update_goal",
]
