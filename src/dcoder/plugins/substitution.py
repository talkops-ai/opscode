"""Variable substitution for plugin-provided configuration in DCoder."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from dcoder.plugins.models import JsonValue


def plugin_environment(
    *, plugin_root: Path, plugin_data: Path, project_dir: Path | None = None
) -> dict[str, str]:
    """Build environment variables exposed to plugin subprocesses."""
    root = str(plugin_root)
    data = str(plugin_data)
    env = {
        "DCODER_PLUGIN_ROOT": root,
        "DCODER_PLUGIN_DATA": data,
        "CLAUDE_PLUGIN_ROOT": root,
        "CLAUDE_PLUGIN_DATA": data,
        "PLUGIN_ROOT": root,
        "PLUGIN_DATA": data,
    }
    if project_dir is not None:
        env["DCODER_PROJECT_DIR"] = str(project_dir)
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return env


def substitute_string(
    value: str, *, plugin_root: Path, plugin_data: Path, project_dir: Path | None = None
) -> str:
    """Substitute plugin path variables in a string."""
    env = plugin_environment(
        plugin_root=plugin_root, plugin_data=plugin_data, project_dir=project_dir
    )
    result = value
    for key, replacement in env.items():
        result = result.replace(f"${{{key}}}", replacement)
    return result


def substitute_json(
    value: JsonValue,
    *,
    plugin_root: Path,
    plugin_data: Path,
    project_dir: Path | None = None,
) -> JsonValue:
    """Substitute plugin variables throughout a JSON-compatible value."""
    if isinstance(value, str):
        return substitute_string(
            value,
            plugin_root=plugin_root,
            plugin_data=plugin_data,
            project_dir=project_dir,
        )
    if isinstance(value, list):
        return [
            substitute_json(
                item,
                plugin_root=plugin_root,
                plugin_data=plugin_data,
                project_dir=project_dir,
            )
            for item in value
        ]
    if isinstance(value, dict):
        return {
            key: substitute_json(
                item,
                plugin_root=plugin_root,
                plugin_data=plugin_data,
                project_dir=project_dir,
            )
            for key, item in value.items()
        }
    return value
