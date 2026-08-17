"""OpsCode middleware modules and centralized registry onboarding."""

from __future__ import annotations

from typing import TYPE_CHECKING

from opscode.middleware.registry import (
    MiddlewareRegistry,
    register_middleware,
    get_middleware_registry,
)

# Custom-built middlewares imported in insertion execution order
from opscode.middleware.configurable_model import ConfigurableModelMiddleware
from opscode.middleware.local_context import LocalContextMiddleware
from opscode.middleware.glm_stall_recovery import GlmTerminalStallRecoveryMiddleware
from opscode.middleware.ask_user import AskUserMiddleware
from opscode.middleware.resume_state import ResumeStateMiddleware
from opscode.middleware.memory_guard import ManagedMemoryGuardMiddleware
from opscode.middleware.compaction import CLICompactionMiddleware, _create_cli_compaction_middleware
from opscode.middleware.skills import PluginSkillsMiddleware
from opscode.middleware.tool_filter import ToolFilterMiddleware
from opscode.middleware.headless_mcp_guard import (
    HeadlessMCPGuardMiddleware,
    gated_mcp_tool_names,
    mcp_tool_is_coherently_read_only,
)
from opscode.middleware.shell_allow_list import ShellAllowListMiddleware
from opscode.middleware.cost_tracking import CostTrackingMiddleware, CostState
from opscode.middleware.auto_mode import AutoModeHITLMiddleware
from opscode.middleware.subagents import SubagentsMiddleware
from opscode.middleware.unified_system_message import UnifiedSystemMessageMiddleware, unify_system_message

# Type-only imports so checkers see proper class types for lazy-loaded names.
if TYPE_CHECKING:
    from opscode.middleware.goal_tools import GoalToolsMiddleware as GoalToolsMiddleware
    from opscode.middleware.goal_criteria import GoalCriteriaMiddleware as GoalCriteriaMiddleware
    from opscode.middleware.reliable_rubric import ReliableRubricMiddleware as ReliableRubricMiddleware


# Runtime lazy imports to break circular dependency:
#   tools.goal_tools → middleware.resume_state → middleware.__init__
#     → middleware.goal_tools → tools.goal_tools (still initializing)

def __getattr__(name: str) -> object:
    if name == "GoalToolsMiddleware":
        from opscode.middleware.goal_tools import GoalToolsMiddleware
        return GoalToolsMiddleware
    if name == "GoalCriteriaMiddleware":
        from opscode.middleware.goal_criteria import GoalCriteriaMiddleware
        return GoalCriteriaMiddleware
    if name == "ReliableRubricMiddleware":
        from opscode.middleware.reliable_rubric import ReliableRubricMiddleware
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
    "CostTrackingMiddleware",
    "CostState",
    "ManagedMemoryGuardMiddleware",
    "CLICompactionMiddleware",
    "_create_cli_compaction_middleware",
    "PluginSkillsMiddleware",
    "ToolFilterMiddleware",
    "HeadlessMCPGuardMiddleware",
    "gated_mcp_tool_names",
    "mcp_tool_is_coherently_read_only",
    "ShellAllowListMiddleware",
    "AutoModeHITLMiddleware",
    "SubagentsMiddleware",
    "GoalCriteriaMiddleware",
    "ReliableRubricMiddleware",
    "UnifiedSystemMessageMiddleware",
    "unify_system_message",
]
