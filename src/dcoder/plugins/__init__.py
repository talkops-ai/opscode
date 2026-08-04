"""DCoder Plugin System.

Provides plugin discovery, marketplace management, and plugin protocol
for extending DCoder with new skills, MCP servers, and capabilities.
"""

from __future__ import annotations

import importlib.metadata
import logging
from typing import Any, Protocol

from dcoder.plugins.discovery import (
    add_local_marketplace,
    add_marketplace_source,
    discover_plugins as discover_marketplace_plugins,
    install_plugin,
    list_available_plugins,
    list_installed_plugin_ids,
    remove_marketplace,
    set_installed_plugin_enabled,
    uninstall_plugin,
)
from dcoder.plugins.models import PluginDiscoveryResult, PluginInstance
from dcoder.ui.command_registry import SlashCommand

logger = logging.getLogger(__name__)


class DCoderPlugin(Protocol):
    """Protocol interface that external python plugins may implement."""

    name: str

    def register_commands(self) -> list[SlashCommand]:
        """Return custom slash commands registered by this plugin."""
        ...

    def register_tools(self) -> list[Any]:
        """Return custom tools registered by this plugin."""
        ...

    def register_renderers(self) -> dict[str, Any]:
        """Return custom tool renderers registered by this plugin."""
        ...

    def get_theme_overrides(self) -> dict[str, str] | None:
        """Return custom theme overrides if provided."""
        ...


class TerraformPlugin:
    """Built-in plugin for Terraform infrastructure tooling."""

    name = "terraform"

    def register_commands(self) -> list[SlashCommand]:
        return []

    def register_tools(self) -> list[Any]:
        return []

    def register_renderers(self) -> dict[str, Any]:
        return {}

    def get_theme_overrides(self) -> dict[str, str] | None:
        return None


def discover_plugins() -> list[DCoderPlugin]:
    """Discover and return all active Python plugins (built-in + entrypoints)."""
    plugins: list[DCoderPlugin] = [TerraformPlugin()]
    try:
        eps = importlib.metadata.entry_points(group="dcoder.plugins")
        for ep in eps:
            try:
                plugin_cls = ep.load()
                plugins.append(plugin_cls())
            except Exception as e:
                logger.warning("Failed to load plugin entry point %s: %s", ep.name, e)
    except Exception:
        pass
    return plugins


from dcoder.plugins.commands_cli import (
    execute_plugin_command,
    setup_plugin_parser,
)

__all__ = [
    "DCoderPlugin",
    "PluginDiscoveryResult",
    "PluginInstance",
    "TerraformPlugin",
    "add_local_marketplace",
    "add_marketplace_source",
    "discover_marketplace_plugins",
    "discover_plugins",
    "execute_plugin_command",
    "install_plugin",
    "list_available_plugins",
    "list_installed_plugin_ids",
    "remove_marketplace",
    "set_installed_plugin_enabled",
    "setup_plugin_parser",
    "uninstall_plugin",
]
