"""Variable substitution for plugin-provided configuration in OpsCode."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from opscode.plugins.models import JsonValue

# Pattern matching ${VAR_NAME} for fallback env-var expansion
_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def plugin_environment(
    *, plugin_root: Path, plugin_data: Path, project_dir: Path | None = None
) -> dict[str, str]:
    """Build environment variables exposed to plugin subprocesses."""
    root = str(plugin_root)
    data = str(plugin_data)
    env = {
        "OPSCODE_PLUGIN_ROOT": root,
        "OPSCODE_PLUGIN_DATA": data,
        "CLAUDE_PLUGIN_ROOT": root,
        "CLAUDE_PLUGIN_DATA": data,
        "PLUGIN_ROOT": root,
        "PLUGIN_DATA": data,
    }
    if project_dir is not None:
        project = str(project_dir)
        env["OPSCODE_PROJECT_DIR"] = project
        env["CLAUDE_PROJECT_DIR"] = project
        # Aliases expected by the audit / Claude Code compatibility
        env["PROJECT_DIR"] = project
        env["WORKSPACE_ROOT"] = project
    return env


def substitute_string(
    value: str, *, plugin_root: Path, plugin_data: Path, project_dir: Path | None = None
) -> str:
    """Substitute plugin path variables in a string.

    After all known plugin variables are replaced, any remaining ``${VAR}``
    patterns are resolved from ``os.environ`` (fallback env-var expansion).
    """
    env = plugin_environment(
        plugin_root=plugin_root, plugin_data=plugin_data, project_dir=project_dir
    )
    result = value
    for key, replacement in env.items():
        result = result.replace(f"${{{key}}}", replacement)

    # Fallback: expand remaining ${VAR} from os.environ
    def _env_replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    result = _ENV_VAR_RE.sub(_env_replace, result)
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

