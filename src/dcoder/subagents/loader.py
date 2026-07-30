"""Loader for custom subagent definitions from the filesystem."""

from __future__ import annotations

import logging
import re
import yaml
from pathlib import Path
from dcoder.subagents.types import SubagentMetadata

logger = logging.getLogger(__name__)

def _parse_subagent_file(
    file_path: Path, *, fallback_name: str | None = None
) -> SubagentMetadata | None:
    """Parse a subagent markdown file with YAML frontmatter."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Skipping subagent %s: could not read file (%s)", file_path, exc)
        return None

    # Extract YAML frontmatter (--- delimited)
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", content, re.DOTALL)
    if not match:
        logger.warning(
            "Skipping subagent %s: missing YAML frontmatter.",
            file_path,
        )
        return None

    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        logger.warning(
            "Skipping subagent %s: invalid YAML frontmatter (%s)", file_path, exc
        )
        return None

    if not isinstance(frontmatter, dict):
        logger.warning(
            "Skipping subagent %s: frontmatter must be a mapping.",
            file_path,
        )
        return None

    name_value = frontmatter.get("name", fallback_name)
    description_value = frontmatter.get("description")
    model = frontmatter.get("model")

    name = name_value.strip() if isinstance(name_value, str) and name_value.strip() else None
    description = description_value.strip() if isinstance(description_value, str) and description_value.strip() else None
    model_valid = model is None or isinstance(model, str)

    if name is None or description is None or not model_valid:
        return None

    return {
        "name": name,
        "description": description,
        "system_prompt": match.group(2).strip(),
        "model": model,
        "source": "",
        "path": str(file_path),
    }

def _load_subagents_from_dir(
    agents_dir: Path, source: str
) -> dict[str, SubagentMetadata]:
    """Load subagents from a directory containing folders with AGENTS.md."""
    subagents: dict[str, SubagentMetadata] = {}
    if not agents_dir.exists() or not agents_dir.is_dir():
        return subagents

    for entry in agents_dir.iterdir():
        if not entry.is_dir():
            continue

        subagent_file = entry / "AGENTS.md"
        if not subagent_file.exists():
            continue

        subagent = _parse_subagent_file(subagent_file, fallback_name=entry.name)
        if subagent:
            subagent["source"] = source
            subagents[subagent["name"]] = subagent

    return subagents

def list_subagents(
    *,
    user_agents_dir: Path | None = None,
    project_agents_dir: Path | None = None,
) -> list[SubagentMetadata]:
    """List subagents from user and project directories, with project overriding user."""
    all_subagents: dict[str, SubagentMetadata] = {}

    # Load user subagents (lower priority)
    if user_agents_dir is not None:
        all_subagents.update(_load_subagents_from_dir(user_agents_dir, "user"))

    # Load project subagents (override user)
    if project_agents_dir is not None:
        all_subagents.update(_load_subagents_from_dir(project_agents_dir, "project"))

    return list(all_subagents.values())
