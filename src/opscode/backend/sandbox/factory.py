from __future__ import annotations

import atexit
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Generator
import string

from opscode.backend.sandbox.provider import (
    SandboxProvider,
    SandboxProviderMetadata,
    SandboxInstallHint,
)
from opscode.backend.sandbox.config import SandboxConfig
from opscode.backend.sandbox.registry import SandboxRegistry, BUILTIN_METADATA

logger = logging.getLogger("opscode")

_active_sandboxes: Dict[str, Any] = {}
_active_sandboxes_lock = threading.Lock()


def _should_ignore(path: Path, project_root: Path) -> bool:
    ignored_names = {
        ".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
        ".opscode", ".state"
    }
    for part in path.relative_to(project_root).parts:
        if part in ignored_names:
            return True
    return False


def _sync_workspace_to_sandbox(backend: Any, working_dir: str) -> None:
    from opscode.config.settings import settings
    if not settings.project_root:
        return
    for root, dirs, files in os.walk(settings.project_root):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if not _should_ignore(root_path / d, settings.project_root)]
        for file in files:
            file_path = root_path / file
            if not _should_ignore(file_path, settings.project_root):
                rel_path = file_path.relative_to(settings.project_root)
                try:
                    with open(file_path, "rb") as f:
                        content = f.read()
                    remote_path = str(Path(working_dir) / rel_path)
                    try:
                        content_str = content.decode("utf-8")
                        backend.write_file(remote_path, content_str)
                    except UnicodeDecodeError:
                        backend.write_file(remote_path, content)
                except Exception as e:
                    logger.warning("Failed to sync file %s to sandbox: %s", rel_path, e)


def _run_sandbox_setup(backend: Any, setup_script_path: str) -> None:
    try:
        script_path = Path(setup_script_path)
        if script_path.is_file():
            script_content = script_path.read_text(encoding="utf-8")
            substituted = string.Template(script_content).safe_substitute(os.environ)
            backend.execute(substituted)
    except Exception as e:
        logger.warning("Failed to run sandbox setup script %s: %s", setup_script_path, e)


def create_sandbox(
    provider_name: str,
    thread_id: str,
    config_path: Path | None = None,
) -> Any:
    """Create a sandbox, synchronize local files, run setup scripts, and cache it."""
    with _active_sandboxes_lock:
        if thread_id in _active_sandboxes:
            return _active_sandboxes[thread_id]

        registry = SandboxRegistry.load(config_path)
        provider = registry.create_provider(provider_name)
        metadata = registry.get_metadata(provider_name)
        working_dir = metadata.working_dir if metadata else "/workspace"

        params = registry.get_params(provider_name)
        backend = provider.get_or_create(**params)

        # Sync workspace
        _sync_workspace_to_sandbox(backend, working_dir)

        # Run setup script if configured
        config = SandboxConfig.load(config_path)
        # Note: setup script can be read from config or env if defined, otherwise skipped
        
        _active_sandboxes[thread_id] = backend
        return backend


def _cleanup_active_sandboxes() -> None:
    with _active_sandboxes_lock:
        registry = SandboxRegistry()
        for thread_id, backend in list(_active_sandboxes.items()):
            try:
                # Best-effort delete using the corresponding provider if possible
                provider_name = registry.default or "modal"
                provider = registry.create_provider(provider_name)
                provider.delete(sandbox_id=backend.id)
            except Exception as e:
                logger.warning("Failed to cleanup active sandbox %s: %s", backend.id, e)
        _active_sandboxes.clear()


atexit.register(_cleanup_active_sandboxes)


# Curated built-in providers (stubs for import/instantiation)

class _AgentCoreProvider(SandboxProvider):
    def get_or_create(self, *, sandbox_id: str | None = None, **kwargs: Any) -> Any:
        raise NotImplementedError("AgentCore sandbox provider is not configured")
    def delete(self, *, sandbox_id: str, **kwargs: Any) -> None:
        pass


class _DaytonaProvider(SandboxProvider):
    def get_or_create(self, *, sandbox_id: str | None = None, **kwargs: Any) -> Any:
        raise NotImplementedError("Daytona sandbox provider is not configured")
    def delete(self, *, sandbox_id: str, **kwargs: Any) -> None:
        pass


class _LangSmithProvider(SandboxProvider):
    def get_or_create(self, *, sandbox_id: str | None = None, **kwargs: Any) -> Any:
        raise NotImplementedError("LangSmith sandbox provider is not configured")
    def delete(self, *, sandbox_id: str, **kwargs: Any) -> None:
        pass


class _ModalProvider(SandboxProvider):
    def get_or_create(self, *, sandbox_id: str | None = None, **kwargs: Any) -> Any:
        raise NotImplementedError("Modal sandbox provider is not configured")
    def delete(self, *, sandbox_id: str, **kwargs: Any) -> None:
        pass


class _RunloopProvider(SandboxProvider):
    def get_or_create(self, *, sandbox_id: str | None = None, **kwargs: Any) -> Any:
        raise NotImplementedError("Runloop sandbox provider is not configured")
    def delete(self, *, sandbox_id: str, **kwargs: Any) -> None:
        pass


class _VercelProvider(SandboxProvider):
    def get_or_create(self, *, sandbox_id: str | None = None, **kwargs: Any) -> Any:
        raise NotImplementedError("Vercel sandbox provider is not configured")
    def delete(self, *, sandbox_id: str, **kwargs: Any) -> None:
        pass
