"""Parser for built-in subagent bundle directories and plugin-style subagent assets."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from opscode.subagents.loader import _parse_subagent_file
from opscode.subagents.types import SubagentMetadata

logger = logging.getLogger(__name__)


def _discover_local_skill_names(skills_dir: Path) -> list[str]:
    """Discover all skill names from SKILL.md frontmatter and directory names under skills_dir."""
    if not skills_dir.exists() or not skills_dir.is_dir():
        return []

    names: set[str] = set()
    for entry in skills_dir.rglob("SKILL.md"):
        if entry.is_file():
            names.add(entry.parent.name)
            try:
                content = entry.read_text(encoding="utf-8")
                match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)
                if match:
                    import yaml

                    frontmatter = yaml.safe_load(match.group(1))
                    if isinstance(frontmatter, dict) and frontmatter.get("name"):
                        declared_name = str(frontmatter["name"]).strip()
                        if declared_name:
                            names.add(declared_name)
            except Exception as exc:
                logger.debug("Could not parse SKILL.md at %s: %s", entry, exc)

    return sorted(names)


def parse_subagent_bundle(
    bundle_dir: Path, source: str = "built-in"
) -> list[SubagentMetadata]:
    """Parse a single subagent bundle directory (containing agents/, skills/, and optional .mcp.json)."""
    subagents: list[SubagentMetadata] = []
    if not bundle_dir.exists() or not bundle_dir.is_dir():
        return subagents

    agents_dir = bundle_dir / "agents"
    agent_files: list[Path] = []

    if agents_dir.exists() and agents_dir.is_dir():
        for entry in agents_dir.iterdir():
            if entry.is_file() and entry.suffix.lower() == ".md":
                agent_files.append(entry)
            elif entry.is_dir():
                sub_agents_file = entry / "AGENTS.md"
                if sub_agents_file.is_file():
                    agent_files.append(sub_agents_file)
    else:
        # Fallback to direct AGENTS.md at bundle root if agents/ subfolder omitted
        direct_file = bundle_dir / "AGENTS.md"
        if direct_file.is_file():
            agent_files.append(direct_file)

    skills_dir = bundle_dir / "skills"
    local_skill_names = _discover_local_skill_names(skills_dir)
    mcp_file = bundle_dir / ".mcp.json"
    has_mcp = mcp_file.exists() and mcp_file.is_file()

    for file_path in agent_files:
        meta = _parse_subagent_file(file_path, fallback_name=bundle_dir.name)
        if not meta:
            continue

        meta["source"] = source
        meta["path"] = str(file_path)

        # If subagent frontmatter omitted skills, default strictly to local bundle skills
        if not meta.get("skills") and local_skill_names:
            meta["skills"] = list(local_skill_names)

        # Attach optional bundle .mcp.json
        if has_mcp and "mcp_files" not in meta and "mcp_config" not in meta:
            meta["mcp_files"] = [str(mcp_file)]

        subagents.append(meta)

    return subagents


def parse_built_in_subagents(
    built_in_root: Path | None = None,
) -> list[SubagentMetadata]:
    """Discover and parse all built-in subagent bundles from `src/opscode/built_in_subagents/`."""
    if built_in_root is None:
        built_in_root = Path(__file__).parent.parent / "built_in_subagents"

    subagents: list[SubagentMetadata] = []
    if not built_in_root.exists() or not built_in_root.is_dir():
        return subagents

    for entry in sorted(built_in_root.iterdir()):
        if entry.is_dir():
            parsed = parse_subagent_bundle(entry, source="built-in")
            subagents.extend(parsed)

    return subagents
