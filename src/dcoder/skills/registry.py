"""Skill registry to discover, validate, and index dcoder skills."""

import logging
import re
import threading
from pathlib import Path
from typing import TypedDict, Any, cast
from dcoder.config.settings import settings
from dcoder.skills.loader import list_skills

logger = logging.getLogger("dcoder")


class SkillMetadata(TypedDict):
    name: str
    description: str
    domain: str
    path: str
    virtual_path: str
    frontmatter: dict[str, Any]
    system_prompt: str

class SkillRegistry:
    """Discovers and indexes skills from system, user, and project directories."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._skills: dict[str, SkillMetadata] = {}

    @classmethod
    def get_instance(cls) -> "SkillRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def discover_skills(self, force: bool = False) -> None:
        """Scan all skill directories and parse SKILL.md files."""
        if self._skills and not force:
            return

        built_in_dir = Path(__file__).parent.parent / "built_in_skills"
        user_skills_dir = settings.get_user_skills_dir("dcoder")
        project_skills_dir = settings.get_project_skills_dir()

        # Build list of directories to discover
        discovered = list_skills(
            built_in_skills_dir=built_in_dir,
            user_skills_dir=user_skills_dir,
            project_skills_dir=project_skills_dir,
        )

        name_pattern = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
        
        new_skills = {}
        for skill in discovered:
            name = skill.get("name", "")
            # Name validation
            if not name or len(name) > 64 or not name_pattern.match(name):
                # Ignore invalid skill names
                continue

            path = skill.get("path", "")
            # Path traversal validation
            try:
                resolved_path = Path(path).resolve()
                # Must be relative to one of our roots
                roots = [built_in_dir, user_skills_dir]
                if project_skills_dir:
                    roots.append(project_skills_dir)
                
                is_safe = False
                for root in roots:
                    try:
                        resolved_root = root.expanduser().resolve()
                        if resolved_path.is_relative_to(resolved_root):
                            is_safe = True
                            break
                    except Exception:
                        pass
                if not is_safe:
                    continue
            except Exception:
                continue

            new_skills[name] = SkillMetadata(
                name=name,
                description=skill.get("description") or "",
                domain=skill.get("metadata", {}).get("domain") or "DevOps",
                path=str(resolved_path),
                virtual_path=f"/skills/{name}/SKILL.md",
                frontmatter=cast(dict[str, Any], skill.get("metadata") or {}),
                system_prompt=str(skill.get("system_prompt") or ""),
            )
        self._skills = new_skills

    def get_sources_for_middleware(self) -> list[tuple[str, ...]]:
        """Return sources formatted as (path, label) or (path, label, namespace) for SkillsMiddleware."""
        built_in_dir = Path(__file__).parent.parent / "built_in_skills"
        user_skills_dir = settings.get_user_skills_dir("dcoder")

        sources: list[tuple[str, ...]] = [
            (str(built_in_dir), "Built-in"),
            (str(user_skills_dir), "User"),
        ]
        if settings.project_root:
            project_skills_dir = settings.project_root / ".dcoder" / "skills"
            sources.append((str(project_skills_dir), "Project"))

        # Include plugin-supplied skill directories
        try:
            from dcoder.plugins import discover_marketplace_plugins

            result = discover_marketplace_plugins()
            for plugin in result.plugins:
                root = getattr(plugin, "root", None)
                if root and isinstance(root, Path):
                    skills_dir = root / "skills"
                    if skills_dir.is_dir():
                        p_id = getattr(plugin, "plugin_id", getattr(plugin, "name", "plugin"))
                        sources.append(
                            (
                                str(skills_dir),
                                f"Plugin: {p_id}",
                                p_id,
                            )
                        )
        except Exception as exc:
            logger.warning("Could not discover plugin skills for middleware: %s", exc)


        return [source for source in sources if Path(source[0]).exists()]




    def get_skill(self, name: str) -> SkillMetadata | None:
        self.discover_skills()
        return self._skills.get(name)
