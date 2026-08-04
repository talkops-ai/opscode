"""Adapter from discovered plugins to DCoder subagent metadata."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dcoder.plugins.models import PluginInstance
    from dcoder.subagents.types import SubagentMetadata

logger = logging.getLogger(__name__)


def plugin_subagents(plugins: tuple[PluginInstance, ...]) -> list[SubagentMetadata]:
    """Discover and parse subagents from enabled plugins."""
    from dcoder.subagents.loader import _parse_subagent_file

    subagents: list[SubagentMetadata] = []

    for plugin in plugins:
        p_id = plugin.plugin_id
        for agent_path in plugin.inventory.agents:
            if not agent_path.exists():
                continue
            if agent_path.is_dir():
                # Scan for .md files or AGENTS.md in subdirectory
                for entry in agent_path.iterdir():
                    if entry.is_file() and entry.suffix == ".md":
                        meta = _parse_subagent_file(entry, fallback_name=entry.stem)
                        if meta:
                            meta["name"] = f"{p_id}:{meta['name']}"
                            meta["source"] = f"plugin:{p_id}"
                            subagents.append(meta)
                    elif entry.is_dir():
                        sub_agents_file = entry / "AGENTS.md"
                        if sub_agents_file.is_file():
                            meta = _parse_subagent_file(sub_agents_file, fallback_name=entry.name)
                            if meta:
                                meta["name"] = f"{p_id}:{meta['name']}"
                                meta["source"] = f"plugin:{p_id}"
                                subagents.append(meta)
            elif agent_path.is_file() and agent_path.suffix == ".md":
                meta = _parse_subagent_file(agent_path, fallback_name=agent_path.stem)
                if meta:
                    meta["name"] = f"{p_id}:{meta['name']}"
                    meta["source"] = f"plugin:{p_id}"
                    subagents.append(meta)

    return subagents


def discover_plugin_subagents() -> list[SubagentMetadata]:
    """Discover subagent definitions across all enabled marketplace plugins."""
    try:
        from dcoder.plugins.discovery import discover_plugins

        plugins = discover_plugins().plugins
        return plugin_subagents(plugins)
    except Exception as exc:
        logger.warning("Could not discover plugin subagents: %s", exc)
        return []
