"""Adapter from discovered plugins to OpsCode skill sources."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from opscode.plugins.models import PluginInstance

logger = logging.getLogger(__name__)

SkillPath: TypeAlias = str
SkillLabel: TypeAlias = str
SkillNamespace: TypeAlias = str
PluginSkillSource: TypeAlias = tuple[SkillPath, SkillLabel, SkillNamespace]


def namespaced_skill_name(
    namespace: SkillNamespace,
    name: str,
    subfolders: tuple[str, ...] = (),
) -> str:
    """Qualify a skill name under its plugin namespace."""
    return ":".join((namespace, *subfolders, name)).lower()


def plugin_skill_sources(
    plugins: tuple[PluginInstance, ...],
) -> list[PluginSkillSource]:
    """Return skill source tuples for plugin skills."""
    sources: list[PluginSkillSource] = []
    for plugin in plugins:
        for path in plugin.inventory.skills:
            source_path = path.parent if path.name == "SKILL.md" else path
            try:
                if not source_path.exists():
                    continue
            except OSError:
                logger.warning("Could not inspect plugin skill path %s", source_path)
                continue
            sources.append(
                (
                    str(source_path),
                    f"Plugin: {plugin.plugin_id}",
                    plugin.plugin_id,
                )
            )
    return sources


def plugin_skill_roots(plugins: tuple[PluginInstance, ...]) -> list[Path]:
    """Return plugin skill roots for skill-content containment checks."""
    roots: list[Path] = []
    for plugin in plugins:
        roots.extend(
            path.parent if path.name == "SKILL.md" else path
            for path in plugin.inventory.skills
        )
    return roots


def discover_plugin_skill_state() -> tuple[
    tuple[tuple[Path, str], ...], tuple[Path, ...], frozenset[str]
]:
    """Discover plugin skill sources, containment roots, and loaded ids."""
    plugin_sources: tuple[tuple[Path, str], ...] = ()
    plugin_roots: tuple[Path, ...] = ()
    plugin_ids: frozenset[str] = frozenset()
    try:
        from opscode.plugins.discovery import discover_plugins

        plugins = discover_plugins().plugins
        plugin_sources = tuple(
            (Path(path), namespace)
            for path, _label, namespace in plugin_skill_sources(plugins)
        )
        plugin_roots = tuple(plugin_skill_roots(plugins))
        plugin_ids = frozenset(plugin.plugin_id for plugin in plugins)
    except (OSError, RuntimeError):
        logger.warning("Could not discover plugin skills", exc_info=True)
        return (), (), frozenset()

    return plugin_sources, plugin_roots, plugin_ids


def discover_plugin_skill_sources_and_roots() -> tuple[
    tuple[tuple[Path, str], ...], tuple[Path, ...]
]:
    """Discover plugin skill sources and containment roots."""
    plugin_sources, plugin_roots, _plugin_ids = discover_plugin_skill_state()

    return plugin_sources, plugin_roots
