"""Trust store for project-level MCP server configurations.

Manages persistent approval of project-level MCP configs that contain stdio
servers (which execute local commands). Trust is fingerprint-based: if the
config content changes, the user must re-approve.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from opscode.config.paths import MCP_TRUST_PATH

logger = logging.getLogger("opscode")

_STORAGE_VERSION = 1


def _default_store_path() -> Path:
    """Return `~/.opscode/.state/mcp_trust.json`."""
    return MCP_TRUST_PATH


def compute_config_fingerprint(config_paths: list[Path]) -> str:
    """Compute a SHA-256 fingerprint over sorted, concatenated config contents."""
    hasher = hashlib.sha256()
    for path in sorted(config_paths):
        try:
            hasher.update(path.read_bytes())
        except OSError:
            logger.warning("Could not read %s for fingerprinting", path, exc_info=True)
    return f"sha256:{hasher.hexdigest()}"


def _load_store(store_path: Path) -> dict[str, Any]:
    """Read the JSON trust store file."""
    try:
        if not store_path.exists():
            return {}
        data = json.loads(store_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning(
            "MCP trust store %s is corrupt; treating as empty: %s", store_path, exc
        )
        return {}
    except OSError as exc:
        logger.warning(
            "Could not read MCP trust store %s; treating as empty: %s",
            store_path,
            exc,
        )
        return {}
    if not isinstance(data, dict):
        logger.warning("MCP trust store %s is not a JSON object; ignoring", store_path)
        return {}
    return data


def _save_store(data: dict[str, Any], store_path: Path) -> bool:
    """Atomic write of JSON trust data to `store_path`."""
    try:
        store_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=store_path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            Path(tmp_path).replace(store_path)
        except BaseException:
            with contextlib.suppress(OSError):
                Path(tmp_path).unlink()
            raise
    except (OSError, ValueError):
        logger.exception("Failed to save MCP trust store to %s", store_path)
        return False
    return True


def _read_projects(store_path: Path) -> dict[str, Any]:
    """Return the `projects` mapping from the store, or an empty dict."""
    projects = _load_store(store_path).get("projects", {})
    return projects if isinstance(projects, dict) else {}


def is_project_mcp_trusted(
    project_root: str,
    fingerprint: str,
    *,
    store_path: Path | None = None,
) -> bool:
    """Check whether a project's MCP config is trusted with the given fingerprint."""
    if store_path is None:
        store_path = _default_store_path()
    return _read_projects(store_path).get(project_root) == fingerprint


def trust_project_mcp(
    project_root: str,
    fingerprint: str,
    *,
    store_path: Path | None = None,
) -> bool:
    """Persist trust for a project's MCP config."""
    if store_path is None:
        store_path = _default_store_path()

    data = _load_store(store_path)
    projects = data.get("projects")
    if not isinstance(projects, dict):
        projects = {}
    projects[project_root] = fingerprint
    data["version"] = _STORAGE_VERSION
    data["projects"] = projects
    return _save_store(data, store_path)


def revoke_project_mcp_trust(
    project_root: str,
    *,
    store_path: Path | None = None,
) -> bool:
    """Remove trust for a project's MCP config."""
    if store_path is None:
        store_path = _default_store_path()

    data = _load_store(store_path)
    projects = data.get("projects")
    if not isinstance(projects, dict) or project_root not in projects:
        return True
    del projects[project_root]
    data["version"] = _STORAGE_VERSION
    data["projects"] = projects
    return _save_store(data, store_path)
