"""Loader for custom subagent definitions from the filesystem and config."""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any, TypedDict

import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

from dcoder.subagents.types import SubagentMetadata

logger = logging.getLogger(__name__)


def _parse_subagent_file(
    file_path: Path, *, fallback_name: str | None = None
) -> SubagentMetadata | None:
    """Parse a subagent markdown file with YAML frontmatter.

    The file must have YAML frontmatter (delimited by ---) containing at minimum
    a 'description' field. The body of the file becomes the system_prompt.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Skipping subagent %s: could not read file (%s)", file_path, exc)
        return None

    # Extract YAML frontmatter (--- delimited)
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", content, re.DOTALL)
    if not match:
        logger.warning(
            "Skipping subagent %s: missing YAML frontmatter. The file must start "
            "with a '---' delimited block containing at least 'description'.",
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
            "Skipping subagent %s: frontmatter must be a mapping with a "
            "'description' field.",
            file_path,
        )
        return None

    name_value = frontmatter.get("name", fallback_name)
    description_value = frontmatter.get("description")
    model = frontmatter.get("model")
    raw_skills = frontmatter.get("skills")
    raw_tools = frontmatter.get("tools")

    name = (
        name_value.strip()
        if isinstance(name_value, str) and name_value.strip()
        else None
    )
    description = (
        description_value.strip()
        if isinstance(description_value, str) and description_value.strip()
        else None
    )
    model_valid = model is None or isinstance(model, str)

    if name is None or description is None or not model_valid:
        invalid_fields: list[str] = []
        if name is None:
            invalid_fields.append("name (non-empty string required)")
        if description is None:
            invalid_fields.append("description (non-empty string required)")
        if not model_valid:
            invalid_fields.append("model (string required when present)")
        logger.warning(
            "Skipping subagent %s: invalid or missing frontmatter field(s): %s",
            file_path,
            ", ".join(invalid_fields),
        )
        return None

    if "name" not in frontmatter:
        logger.debug(
            "Subagent %s: 'name' omitted from frontmatter; using folder name %r.",
            file_path,
            name,
        )

    skills: list[str] | None = (
        [str(s) for s in raw_skills] if isinstance(raw_skills, list) else None
    )
    tools: list[str] | None = (
        [str(t) for t in raw_tools] if isinstance(raw_tools, list) else None
    )

    return {
        "name": name,
        "description": description,
        "system_prompt": match.group(2).strip(),
        "model": model,
        "skills": skills,
        "tools": tools,
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
            if entry.suffix.lower() == ".md":
                logger.warning(
                    "Ignoring %s subagent file %s: subagents must be defined at "
                    "%s/{subagent-name}/AGENTS.md, not as a file directly in the "
                    "agents directory.",
                    source,
                    entry,
                    agents_dir,
                )
            continue

        subagent_file = entry / "AGENTS.md"
        if not subagent_file.exists():
            stray_md = [p.name for p in entry.glob("*.md")]
            if stray_md:
                logger.warning(
                    "Ignoring %s subagent folder %s: expected an AGENTS.md file "
                    "but found %s. Rename the definition to AGENTS.md.",
                    source,
                    entry,
                    ", ".join(sorted(stray_md)),
                )
            continue

        subagent = _parse_subagent_file(subagent_file, fallback_name=entry.name)
        if subagent:
            subagent["source"] = source
            existing = subagents.get(subagent["name"])
            if existing is not None:
                logger.warning(
                    "Subagent name collision in %s: %s and %s both resolve to "
                    "name=%r. Using %s; give each subagent a unique folder or "
                    "frontmatter 'name'.",
                    agents_dir,
                    existing["path"],
                    subagent["path"],
                    subagent["name"],
                    subagent["path"],
                )
            subagents[subagent["name"]] = subagent

    return subagents


def load_async_subagents(config_path: Path | None = None) -> list[dict[str, Any]]:
    """Load async subagent definitions from `config.toml`.

    Reads the `[async_subagents]` section where each sub-table defines a remote
    LangGraph deployment:

    ```toml
    [async_subagents.researcher]
    description = "Research agent"
    url = "https://my-deployment.langsmith.dev"
    graph_id = "agent"
    ```
    """
    if config_path is None:
        config_path = Path.home() / ".dcoder" / "config.toml"

    if not config_path.exists():
        return []

    try:
        with config_path.open("rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, PermissionError, OSError) as e:
        logger.warning("Could not read async subagents from %s: %s", config_path, e)
        return []

    section = data.get("async_subagents")
    if not isinstance(section, dict):
        return []

    required = {"description", "graph_id"}
    agents: list[dict[str, Any]] = []
    for name, spec in section.items():
        if not isinstance(spec, dict):
            logger.warning("Skipping async subagent '%s': expected a table", name)
            continue
        missing = required - spec.keys()
        if missing:
            logger.warning(
                "Skipping async subagent '%s': missing fields %s", name, sorted(missing)
            )
            continue
        agent: dict[str, Any] = {
            "name": name,
            "description": spec["description"],
            "graph_id": spec["graph_id"],
        }
        if "url" in spec and isinstance(spec["url"], str):
            agent["url"] = spec["url"]
        if "headers" in spec and isinstance(spec["headers"], dict):
            agent["headers"] = spec["headers"]
        agents.append(agent)

    return agents


def list_subagents(
    *,
    user_agents_dir: Path | None = None,
    project_agents_dir: Path | None = None,
    include_plugins: bool = True,
) -> list[SubagentMetadata]:
    """List subagents from plugin, user, and project directories, with project overriding lower tiers."""
    all_subagents: dict[str, SubagentMetadata] = {}

    # Load plugin subagents
    if include_plugins:
        try:
            from dcoder.plugins.adapters.agents import discover_plugin_subagents

            for plugin_subagent in discover_plugin_subagents():
                all_subagents[plugin_subagent["name"]] = plugin_subagent
        except Exception as exc:
            logger.debug("Plugin subagent discovery skipped: %s", exc)

    # Load user subagents (higher priority than plugin)
    if user_agents_dir is not None:
        all_subagents.update(_load_subagents_from_dir(user_agents_dir, "user"))

    # Load project subagents (highest priority)
    if project_agents_dir is not None:
        all_subagents.update(_load_subagents_from_dir(project_agents_dir, "project"))

    return list(all_subagents.values())

