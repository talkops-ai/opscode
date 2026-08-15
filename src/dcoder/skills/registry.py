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
        user_skills_dir = settings.get_user_skills_dir()
        project_skills_dir = settings.get_project_skills_dir()

        # Build list of directories to discover
        discovered = list_skills(
            built_in_skills_dir=built_in_dir,
            user_skills_dir=user_skills_dir,
            project_skills_dir=project_skills_dir,
            project_root=settings.project_root,
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
                from dcoder.config.paths import PLUGINS_DIR
                roots = [built_in_dir, PLUGINS_DIR]
                if user_skills_dir:
                    roots.append(user_skills_dir)
                if project_skills_dir:
                    roots.append(project_skills_dir)
                user_agents_skills = Path.home() / ".agents" / "skills"
                if user_agents_skills.is_dir():
                    roots.append(user_agents_skills)
                user_claude_skills = Path.home() / ".claude" / "skills"
                if user_claude_skills.is_dir():
                    roots.append(user_claude_skills)
                if settings.project_root:
                    roots.append(settings.project_root)
                
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
        """Return sources ordered by lowest to highest precedence (Tier 1 to Tier 7) for SkillsMiddleware."""
        effective_project_root = settings.effective_project_root

        sources: list[tuple[str, ...]] = []

        # Tier 1: Built-in skills
        built_in_dir = Path(__file__).parent.parent / "built_in_skills"
        sources.append((str(built_in_dir), "Built-in"))

        # Tier 2: Plugin skills (namespaced, non-agent plugins only)
        try:
            from dcoder.plugins import discover_marketplace_plugins
            from dcoder.plugins.project_plugins import _has_agents, load_project_plugins

            result = discover_marketplace_plugins(project_root=effective_project_root)
            for plugin in result.plugins:
                if _has_agents(plugin.inventory):
                    continue  # Agent plugin skills are bound exclusively to their subagent
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

            if effective_project_root:
                proj_res = load_project_plugins(effective_project_root)
                for skill_src, label, p_id in proj_res.main_skill_sources:
                    if Path(skill_src).is_dir():
                        sources.append((skill_src, label, p_id))
        except Exception as exc:
            logger.warning("Could not discover plugin skills for middleware: %s", exc)

        # Tier 3: User Deepagents skills (~/.dcoder/skills)
        user_dcoder_dir = settings.get_user_skills_dir()
        if user_dcoder_dir:
            sources.append((str(user_dcoder_dir), "User Deepagents"))

        # Tier 4: User Agents skills (~/.agents/skills)
        user_agents_skills = Path.home() / ".agents" / "skills"
        if user_agents_skills.is_dir():
            sources.append((str(user_agents_skills), "User Agents"))

        # Tier 5: Project Deepagents skills (.dcoder/skills)
        if effective_project_root:
            psd = effective_project_root / ".dcoder" / "skills"
            if psd.is_dir():
                sources.append((str(psd), "Project Deepagents"))

            # Tier 6: Project Agents skills (.agents/skills)
            project_agents_skills = effective_project_root / ".agents" / "skills"
            if project_agents_skills.is_dir():
                sources.append((str(project_agents_skills), "Project Agents"))

        # Tier 7: Claude experimental skills (~/.claude/skills, .claude/skills)
        user_claude_skills = Path.home() / ".claude" / "skills"
        if user_claude_skills.is_dir():
            sources.append((str(user_claude_skills), "Claude Experimental User"))
        if effective_project_root:
            project_claude_skills = effective_project_root / ".claude" / "skills"
            if project_claude_skills.is_dir():
                sources.append((str(project_claude_skills), "Claude Experimental Project"))

        return [source for source in sources if Path(source[0]).exists()]




    def get_skill(self, name: str) -> SkillMetadata | None:
        self.discover_skills()
        return self._skills.get(name)
