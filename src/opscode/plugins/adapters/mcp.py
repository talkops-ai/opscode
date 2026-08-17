"""Adapter from plugin MCP declarations to OpsCode MCP config dictionaries."""

from __future__ import annotations

import json
import logging
import re
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

from opscode.plugins._json import json_object, json_value
from opscode.plugins.substitution import plugin_environment, substitute_json

if TYPE_CHECKING:
    from opscode.plugins.models import JsonObject, JsonValue, PluginInstance

logger = logging.getLogger(__name__)
_MCP_NAME_PART_RE = re.compile(r"[^A-Za-z0-9_-]+")
_MCP_NAME_PART_LENGTH = 48


def _safe_mcp_name_part(value: str) -> str:
    sanitized = _MCP_NAME_PART_RE.sub("_", value).strip("_")
    if sanitized == value and sanitized and len(sanitized) <= _MCP_NAME_PART_LENGTH:
        return sanitized
    digest = sha256(value.encode()).hexdigest()[:8]
    prefix = sanitized[:_MCP_NAME_PART_LENGTH] or "unnamed"
    return f"{prefix}_{digest}"


def scoped_mcp_server_name(plugin_id: str, server_name: str) -> str:
    """Namespace a plugin-declared MCP server's name under its plugin id."""
    plugin_part = _safe_mcp_name_part(plugin_id)
    server_part = _safe_mcp_name_part(server_name)
    return f"plugin__{plugin_part}__{server_part}"


def _mcp_server_needs_login(server: object) -> bool:
    if not isinstance(server, dict):
        return False
    server_type = server.get("type")
    if server_type in {"http", "sse"}:
        return True
    return isinstance(server.get("url"), str)


def plugin_mcp_server_entries(
    plugin: PluginInstance,
) -> tuple[tuple[str, str, bool], ...]:
    """List plugin MCP servers as `(label, scoped_name, needs_login)` tuples."""
    servers: dict[str, object] = {}
    for path in plugin.inventory.mcp_files:
        if path.suffix in {".mcpb", ".dxt"}:
            continue
        servers.update(_load_mcp_server_map(path))
    if plugin.manifest and plugin.manifest.inline_mcp:
        servers.update(_server_map(plugin.manifest.inline_mcp))
    entries: list[tuple[str, str, bool]] = []
    seen: set[str] = set()
    for name, server in servers.items():
        if not isinstance(name, str) or name in seen:
            continue
        seen.add(name)
        entries.append(
            (
                name,
                scoped_mcp_server_name(plugin.plugin_id, name),
                _mcp_server_needs_login(server),
            )
        )
    return tuple(entries)


def _server_map(raw: object) -> JsonObject:
    if not isinstance(raw, dict):
        return {}
    wrapped = raw.get("mcpServers")
    if isinstance(wrapped, dict):
        return json_object(wrapped)
    codex_wrapped = raw.get("mcp_servers")
    if isinstance(codex_wrapped, dict):
        return json_object(codex_wrapped)
    return json_object(raw)


def _load_mcp_server_map(path: Path) -> JsonObject:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Skipping plugin MCP config %s: %s", path, exc)
        return {}
    return _server_map(raw)


def _plugin_mcp_server_map(plugin: PluginInstance) -> JsonObject:
    servers: JsonObject = {}
    for path in plugin.inventory.mcp_files:
        if path.suffix in {".mcpb", ".dxt"}:
            logger.warning(
                "Skipping unsupported MCP bundle for plugin %s: %s",
                plugin.plugin_id,
                path,
            )
            continue
        servers.update(_load_mcp_server_map(path))
    if plugin.manifest and plugin.manifest.inline_mcp:
        servers.update(_server_map(plugin.manifest.inline_mcp))
    return servers


def plugin_mcp_server_names(plugin: PluginInstance) -> tuple[str, ...]:
    """Return scoped MCP server names without preparing plugin runtime state."""
    return tuple(
        scoped_mcp_server_name(plugin.plugin_id, name)
        for name in _plugin_mcp_server_map(plugin)
        if isinstance(name, str)
    )


def _normalize_server(
    server: object, *, plugin: PluginInstance, project_dir: Path | None
) -> JsonValue:
    normalized_server = json_value(server)
    substituted = substitute_json(
        normalized_server,
        plugin_root=plugin.root,
        plugin_data=plugin.data_dir,
        project_dir=project_dir,
    )
    if isinstance(substituted, dict):
        cwd = substituted.get("cwd")
        if isinstance(cwd, str) and cwd and not Path(cwd).is_absolute():
            substituted = {**substituted, "cwd": str((plugin.root / cwd).resolve())}
        env = substituted.get("env")
        plugin_env = plugin_environment(
            plugin_root=plugin.root,
            plugin_data=plugin.data_dir,
            project_dir=project_dir,
        )
        if isinstance(env, dict):
            substituted = {**substituted, "env": {**plugin_env, **env}}
        else:
            substituted = {**substituted, "env": plugin_env}
    return json_value(substituted)


def discover_plugin_mcp_configs(
    *, project_dir: Path | None = None
) -> tuple[JsonObject, ...]:
    """Discover enabled plugins and compose their MCP config layers."""
    try:
        from opscode.plugins.discovery import discover_plugins

        result = discover_plugins()
    except (OSError, RuntimeError):
        logger.warning("Could not discover plugin MCP configs", exc_info=True)
        return ()
    if result.warnings:
        logger.warning(
            "Plugin discovery warnings while loading MCP: %s", result.warnings
        )
    return tuple(plugin_mcp_configs(result.plugins, project_dir=project_dir))


def plugin_mcp_configs(
    plugins: tuple[PluginInstance, ...], *, project_dir: Path | None = None
) -> list[JsonObject]:
    """Build MCP config layers for enabled plugins."""
    configs: list[JsonObject] = []
    for plugin in plugins:
        try:
            plugin.data_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.warning(
                "Could not create plugin data dir for %s: %s",
                plugin.plugin_id,
                plugin.data_dir,
                exc_info=True,
            )
        servers = _plugin_mcp_server_map(plugin)
        scoped: JsonObject = {}
        for name, server in servers.items():
            if not isinstance(name, str):
                continue
            scoped_name = scoped_mcp_server_name(plugin.plugin_id, name)
            scoped[scoped_name] = _normalize_server(
                server, plugin=plugin, project_dir=project_dir
            )
        if scoped:
            configs.append({"mcpServers": scoped})
    return configs
