"""Skill loader for dcoder CLI and middleware."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal, Sequence, cast
from pathlib import Path

from deepagents.backends.filesystem import FilesystemBackend
from deepagents.middleware.skills import (
    SkillMetadata,
    _list_skills as list_skills_from_backend,
)

logger = logging.getLogger("dcoder")

class ExtendedSkillMetadata(SkillMetadata):
    """Extended skill metadata for CLI display, adds source tracking."""
    source: Literal["built-in", "user", "project", "plugin"]

def list_skills(
    *,
    built_in_skills_dir: Path | None = None,
    user_skills_dir: Path | None = None,
    project_skills_dir: Path | None = None,
    include_plugins: bool = True,
    project_root: Path | None = None,
) -> list[ExtendedSkillMetadata]:
    """List skills from built-in, user, project, and plugin directories."""
    all_skills: dict[str, ExtendedSkillMetadata] = {}

    sources: list[tuple[Path | None, Literal["built-in", "user", "project", "plugin"], str]] = [
        (built_in_skills_dir, "built-in", ""),
        (user_skills_dir, "user", ""),
        (project_skills_dir, "project", ""),
    ]

    if include_plugins:
        try:
            from dcoder.plugins import discover_marketplace_plugins
            from dcoder.plugins.project_plugins import _has_agents, load_project_plugins

            res = discover_marketplace_plugins(project_root=project_root)
            for plugin in res.plugins:
                if _has_agents(plugin.inventory):
                    continue  # Agent plugin skills belong exclusively to their subagent
                root = getattr(plugin, "root", None)
                if root and isinstance(root, Path):
                    skills_dir = root / "skills"
                    if skills_dir.is_dir():
                        p_id = getattr(plugin, "plugin_id", getattr(plugin, "name", "plugin"))
                        sources.append((skills_dir, "plugin", p_id))

            if project_root:
                proj_res = load_project_plugins(project_root)
                for skill_src, label, p_id in proj_res.main_skill_sources:
                    sd = Path(skill_src)
                    if sd.is_dir():
                        sources.append((sd, "plugin", p_id))
        except Exception as exc:
            logger.debug("Plugin skill discovery skipped in loader: %s", exc)

    for skill_dir, source_label, prefix in sources:
        if not skill_dir or not skill_dir.exists():
            continue
        try:
            backend = FilesystemBackend(root_dir=str(skill_dir), virtual_mode=False)
            skills = list_skills_from_backend(backend=backend, source_path=".")
            for skill in skills:
                name = f"{prefix}:{skill['name']}" if prefix else skill["name"]
                extended = cast("ExtendedSkillMetadata", {
                    **skill,
                    "name": name,
                    "source": source_label
                })
                all_skills[name] = extended
        except Exception:
            logger.warning(
                "Could not load skills from %s",
                skill_dir,
                exc_info=True,
            )

    return list(all_skills.values())

def load_skill_content(
    skill_path: str,
    *,
    allowed_roots: Sequence[Path] = (),
) -> str | None:
    """Read the full raw SKILL.md content for a skill, verifying containment safety."""
    path = Path(skill_path).resolve()

    if allowed_roots:
        resolved_roots = [r.resolve() for r in allowed_roots]
        if not any(path.is_relative_to(root) for root in resolved_roots):
            logger.warning(
                "Skill path %s is outside all allowed roots, refusing to read",
                skill_path,
            )
            msg = (
                f"Skill path {skill_path} resolves outside all allowed skill "
                "directories (SSRF prevention). If this is a symlink, verify its target."
            )
            raise PermissionError(msg)

    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        logger.warning(
            "Could not read skill content from %s", skill_path, exc_info=True
        )
        return None
