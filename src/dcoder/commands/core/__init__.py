"""Core essential command handlers package."""

from dcoder.commands.core.auth import LoginHandler, LogoutHandler
from dcoder.commands.core.bug import BugHandler
from dcoder.commands.core.clear import ClearHandler, ForceClearHandler
from dcoder.commands.core.compact import CompactHandler
from dcoder.commands.core.config_cmd import ConfigHandler
from dcoder.commands.core.context import ContextHandler
from dcoder.commands.core.cost import CostHandler
from dcoder.commands.core.doctor import DoctorHandler
from dcoder.commands.core.effort import EffortHandler
from dcoder.commands.core.exit_cmd import ExitHandler
from dcoder.commands.core.fast import FastHandler
from dcoder.commands.core.help_cmd import HelpHandler
from dcoder.commands.core.mcp import McpHandler
from dcoder.commands.core.model import ModelHandler
from dcoder.commands.core.permissions import PermissionsHandler
from dcoder.commands.core.plugins import PluginsHandler
from dcoder.commands.core.resume import ResumeHandler
from dcoder.commands.core.skills import SkillsHandler

__all__ = [
    "BugHandler",
    "ClearHandler",
    "CompactHandler",
    "ConfigHandler",
    "ContextHandler",
    "CostHandler",
    "DoctorHandler",
    "EffortHandler",
    "ExitHandler",
    "FastHandler",
    "ForceClearHandler",
    "HelpHandler",
    "LoginHandler",
    "LogoutHandler",
    "McpHandler",
    "ModelHandler",
    "PermissionsHandler",
    "PluginsHandler",
    "ResumeHandler",
    "SkillsHandler",
]
