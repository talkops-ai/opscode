import asyncio
import logging

from dcoder.commands._base import BaseCommandHandler, CommandContext, CommandResult
from dcoder.commands._types import BypassTier, CommandCategory, SafetyLevel

logger = logging.getLogger(__name__)


class PluginsHandler(BaseCommandHandler):
    """Handler for /plugins — open plugin manager or list plugins."""

    @property
    def name(self) -> str:
        return "/plugins"

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.CORE

    @property
    def safety_level(self) -> SafetyLevel:
        return SafetyLevel.READ_ONLY

    @property
    def bypass_tier(self) -> BypassTier:
        return BypassTier.QUEUED

    async def execute(self, ctx: CommandContext) -> CommandResult:
        # Try to push a PluginManager screen if available in TUI mode
        if ctx.app and hasattr(ctx.app, "_show_plugin_manager"):
            res = ctx.app._show_plugin_manager()
            if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                await res
            return CommandResult(success=True, message="", mount_as_app_message=False)

        # Fallback: check app._discovered_plugins if set on legacy mock app
        if ctx.app and getattr(ctx.app, "_discovered_plugins", None):
            plugins = ctx.app._discovered_plugins or []
            lines = ["🔌 **Installed Plugins:**\n"]
            for p in plugins:
                name = getattr(p, "name", str(p))
                desc = getattr(p, "description", "")
                status = "✅" if getattr(p, "healthy", True) else "❌"
                lines.append(f"  {status} `{name}`: {desc}")
            return CommandResult(success=True, message="\n".join(lines))

        # Fallback: list discovered marketplace plugins in CLI mode
        from dcoder.plugins import discover_marketplace_plugins, list_available_plugins
        result = discover_marketplace_plugins()
        plugins = result.plugins
        if not plugins:
            available = list_available_plugins()
            if available:
                lines = ["🔌 **Available Plugins:**\n"]
                for p_id, desc, enabled in available:
                    status = "✅" if enabled else "⚪"
                    lines.append(f"  {status} `{p_id}`: {desc}")
                return CommandResult(success=True, message="\n".join(lines))
            return CommandResult(success=True, message="🔌 No plugins installed or discovered.")

        lines = ["🔌 **Installed Plugins:**\n"]
        for p in plugins:
            name = getattr(p, "name", str(p))
            p_id = getattr(p, "plugin_id", name)
            lines.append(f"  ✅ `{p_id}` (v{p.version or '1.0'})")
        return CommandResult(success=True, message="\n".join(lines))




__all__ = ["PluginsHandler"]
