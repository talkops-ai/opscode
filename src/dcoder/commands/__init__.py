"""Command surface framework package for DCoder."""

from dcoder.commands._base import BaseCommandHandler, CommandContext, CommandResult
from dcoder.commands._router import CommandRouter
from dcoder.commands._types import BypassTier, CommandCategory, NotifySeverity, SafetyLevel
from dcoder.commands.registry import CommandRegistry

__all__ = [
    "BaseCommandHandler",
    "BypassTier",
    "CommandCategory",
    "CommandContext",
    "CommandRegistry",
    "CommandResult",
    "CommandRouter",
    "NotifySeverity",
    "SafetyLevel",
]

