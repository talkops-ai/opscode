"""Skills middleware adapter supporting namespaced plugin skills."""

from __future__ import annotations

import logging
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, cast

from deepagents.backends.protocol import FileInfo, LsResult
from deepagents.backends.utils import to_posix_path
from deepagents.middleware import skills as sdk_skills
from deepagents.middleware.skills import SkillsMiddleware

from dcoder.middleware.registry import register_middleware
from dcoder.plugins.adapters.skills import (
    SkillNamespace,
    namespaced_skill_name,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from deepagents.backends.protocol import BackendProtocol
    from langchain_core.runnables import RunnableConfig
    from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)

_PLUGIN_SKILL_SOURCE_LENGTH = 3
_SKILL_FILE = "SKILL.md"


def _entries(ls_result: object) -> list[FileInfo]:
    if isinstance(ls_result, LsResult):
        return list(ls_result.entries or [])
    if isinstance(ls_result, list):
        return cast("list[FileInfo]", ls_result)
    return []


def _child_dirs(entries: list[FileInfo], root: str) -> list[tuple[str, str]]:
    root_posix = PurePosixPath(to_posix_path(root))
    dirs: list[tuple[str, str]] = []
    for entry in entries:
        if not entry.get("is_dir"):
            continue
        path = entry["path"]
        name = PurePosixPath(to_posix_path(path)).name
        if PurePosixPath(to_posix_path(path)) == root_posix:
            continue
        dirs.append((name, path))
    return dirs


def _has_skill_file(entries: list[FileInfo], root: str) -> bool:
    root_posix = PurePosixPath(to_posix_path(root))
    for entry in entries:
        path = PurePosixPath(to_posix_path(entry["path"]))
        if path.name == _SKILL_FILE and path.parent == root_posix:
            return True
    return False


def _skill_md_path(skill_dir: str) -> str:
    return str(PurePosixPath(to_posix_path(skill_dir)) / _SKILL_FILE)


def _namespace_skill(
    skill: sdk_skills.SkillMetadata,
    namespace: SkillNamespace,
    subfolders: tuple[str, ...],
) -> sdk_skills.SkillMetadata:
    return cast(
        "sdk_skills.SkillMetadata",
        {
            **skill,
            "name": namespaced_skill_name(namespace, skill["name"], subfolders),
        },
    )


def discover_skill_dirs(
    backend: BackendProtocol,
    source_path: str,
) -> list[tuple[str, tuple[str, ...]]]:
    found: list[tuple[str, tuple[str, ...]]] = []
    source_root = Path(source_path).resolve()
    visited: set[Path] = set()
    stack: list[tuple[str, tuple[str, ...]]] = [(str(source_root), ())]
    while stack:
        current, path_segments = stack.pop()
        try:
            resolved = Path(current).resolve()
        except (OSError, RuntimeError):
            logger.warning("Could not resolve plugin skill directory %s", current)
            continue
        if not resolved.is_relative_to(source_root) or resolved in visited:
            continue
        visited.add(resolved)
        resolved_path = str(resolved)
        entries = _entries(backend.ls(resolved_path))
        if _has_skill_file(entries, resolved_path):
            found.append((resolved_path, path_segments[:-1]))
            continue
        for name, path in _child_dirs(entries, resolved_path):
            stack.append((path, (*path_segments, name)))
    return found


def load_namespaced_skills(
    backend: BackendProtocol,
    source_path: str,
    namespace: SkillNamespace,
) -> list[sdk_skills.SkillMetadata]:
    skill_dirs = discover_skill_dirs(backend, source_path)
    if not skill_dirs:
        return []
    paths = [_skill_md_path(skill_dir) for skill_dir, _ in skill_dirs]
    responses = backend.download_files(paths)
    skills: list[sdk_skills.SkillMetadata] = []
    for (skill_dir, segments), path, response in zip(
        skill_dirs, paths, responses, strict=True
    ):
        skill = sdk_skills._skill_metadata_from_response(response, skill_dir, path)
        if skill is not None:
            skills.append(_namespace_skill(skill, namespace, segments))
    return skills


@register_middleware(name="skills")
class PluginSkillsMiddleware(SkillsMiddleware):
    """Load namespaced plugin skills with optional whitelist filtering for subagent scoping."""

    def __init__(
        self,
        *,
        backend: BackendProtocol | None = None,
        sources: Sequence[tuple[str, ...]] | None = None,
        system_prompt: str | None = sdk_skills.SKILLS_SYSTEM_PROMPT,
        allowed_skills: Sequence[str] | None = None,
    ) -> None:
        if backend is None:
            from deepagents.backends.filesystem import FilesystemBackend
            backend = FilesystemBackend(virtual_mode=False)
        if sources is None:
            from dcoder.skills.registry import SkillRegistry
            sources = SkillRegistry.get_instance().get_sources_for_middleware()

        sdk_sources = [(source[0], source[1]) for source in sources]
        super().__init__(
            backend=backend,
            sources=sdk_sources,
            system_prompt=system_prompt,
        )
        self._namespaces = tuple(
            source[2] if len(source) == _PLUGIN_SKILL_SOURCE_LENGTH else None
            for source in sources
        )
        self._allowed_skills = tuple(allowed_skills) if allowed_skills is not None else None

    def _is_skill_allowed(self, skill_name: str) -> bool:
        if self._allowed_skills is None:
            return True
        import fnmatch
        for pattern in self._allowed_skills:
            if fnmatch.fnmatch(skill_name, pattern) or fnmatch.fnmatch(skill_name.lower(), pattern.lower()):
                return True
        return False

    def before_agent(
        self,
        state: sdk_skills.SkillsState,
        runtime: Runtime,
        config: RunnableConfig,
    ) -> sdk_skills.SkillsStateUpdate | None:
        if "skills_metadata" in state:
            return None

        backend: BackendProtocol = cast("BackendProtocol", self._backend)
        all_skills: dict[str, sdk_skills.SkillMetadata] = {}
        errors: list[str] = []

        for source_path, _source_label, namespace in zip(
            self.sources, self.source_labels, self._namespaces, strict=True
        ):
            if namespace is None:
                source_skills, source_error = sdk_skills._list_skills_with_errors(
                    backend, source_path
                )
                if source_error is not None:
                    errors.append(source_error)
            else:
                source_skills = load_namespaced_skills(backend, source_path, namespace)
            for skill in source_skills:
                skill_name = skill["name"]
                if self._is_skill_allowed(skill_name):
                    all_skills[skill_name] = skill

        update = sdk_skills.SkillsStateUpdate(skills_metadata=list(all_skills.values()))
        if errors:
            logger.warning("Skills load errors: %s", errors)
            update["skills_load_errors"] = errors
        return update

    async def abefore_agent(
        self,
        state: sdk_skills.SkillsState,
        runtime: Runtime,
        config: RunnableConfig,
    ) -> sdk_skills.SkillsStateUpdate | None:
        import asyncio
        return await asyncio.to_thread(self.before_agent, state, runtime, config)

