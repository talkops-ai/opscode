"""DCoder middleware modules and centralized registry onboarding."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dcoder.middleware.registry import (
    MiddlewareRegistry,
    register_middleware,
    get_middleware_registry,
)

# Custom-built middlewares imported in insertion execution order
from dcoder.middleware.configurable_model import ConfigurableModelMiddleware
from dcoder.middleware.local_context import LocalContextMiddleware
from dcoder.middleware.glm_stall_recovery import GlmTerminalStallRecoveryMiddleware
from dcoder.middleware.ask_user import AskUserMiddleware
from dcoder.middleware.resume_state import ResumeStateMiddleware
from dcoder.middleware.memory_guard import ManagedMemoryGuardMiddleware
from dcoder.middleware.compaction import CLICompactionMiddleware
from dcoder.middleware.skills import PluginSkillsMiddleware
from dcoder.middleware.tool_filter import ToolFilterMiddleware
from dcoder.middleware.headless_mcp_guard import (
    HeadlessMCPGuardMiddleware,
    gated_mcp_tool_names,
    mcp_tool_is_coherently_read_only,
)
from dcoder.middleware.shell_allow_list import ShellAllowListMiddleware
from dcoder.middleware.auto_mode import AutoModeHITLMiddleware

# Type-only imports so checkers see proper class types for lazy-loaded names.
if TYPE_CHECKING:
    from dcoder.middleware.goal_tools import GoalToolsMiddleware as GoalToolsMiddleware
    from dcoder.middleware.goal_criteria import GoalCriteriaMiddleware as GoalCriteriaMiddleware
    from dcoder.middleware.reliable_rubric import ReliableRubricMiddleware as ReliableRubricMiddleware


# Runtime lazy imports to break circular dependency:
#   tools.goal_tools → middleware.resume_state → middleware.__init__
#     → middleware.goal_tools → tools.goal_tools (still initializing)

def __getattr__(name: str) -> object:
    if name == "GoalToolsMiddleware":
        from dcoder.middleware.goal_tools import GoalToolsMiddleware
        return GoalToolsMiddleware
    if name == "GoalCriteriaMiddleware":
        from dcoder.middleware.goal_criteria import GoalCriteriaMiddleware
        return GoalCriteriaMiddleware
    if name == "ReliableRubricMiddleware":
        from dcoder.middleware.reliable_rubric import ReliableRubricMiddleware
        return ReliableRubricMiddleware
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "MiddlewareRegistry",
    "register_middleware",
    "get_middleware_registry",
    "ConfigurableModelMiddleware",
    "LocalContextMiddleware",
    "GlmTerminalStallRecoveryMiddleware",
    "GoalToolsMiddleware",
    "AskUserMiddleware",
    "ResumeStateMiddleware",
    "ManagedMemoryGuardMiddleware",
    "CLICompactionMiddleware",
    "PluginSkillsMiddleware",
    "ToolFilterMiddleware",
    "HeadlessMCPGuardMiddleware",
    "gated_mcp_tool_names",
    "mcp_tool_is_coherently_read_only",
    "ShellAllowListMiddleware",
    "AutoModeHITLMiddleware",
    "GoalCriteriaMiddleware",
    "ReliableRubricMiddleware",
]
