from __future__ import annotations

import importlib
import importlib.metadata
import logging
from typing import TYPE_CHECKING, Any

from opscode.backend.sandbox.config import SandboxConfig
from opscode.backend.sandbox.provider import (
    SandboxInstallHint,
    SandboxProvider,
    SandboxProviderMetadata,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger("opscode")

ENTRY_POINT_GROUP = "opscode.sandbox_providers"

BUILTIN_METADATA: dict[str, SandboxProviderMetadata] = {
    "agentcore": SandboxProviderMetadata(
        name="agentcore",
        working_dir="/tmp",
        install=SandboxInstallHint(kind="extra", name="agentcore"),
        supports_sandbox_id=False,
        backend_module="langchain_agentcore_codeinterpreter",
    ),
    "daytona": SandboxProviderMetadata(
        name="daytona",
        working_dir="/home/daytona",
        install=SandboxInstallHint(kind="extra", name="daytona"),
        backend_module="langchain_daytona",
    ),
    "langsmith": SandboxProviderMetadata(
        name="langsmith",
        working_dir="/root",
        supports_snapshot_name=True,
    ),
    "modal": SandboxProviderMetadata(
        name="modal",
        working_dir="/workspace",
        install=SandboxInstallHint(kind="extra", name="modal"),
        backend_module="langchain_modal",
    ),
    "runloop": SandboxProviderMetadata(
        name="runloop",
        working_dir="/home/user",
        install=SandboxInstallHint(kind="extra", name="runloop"),
        supports_snapshot_name=True,
        backend_module="langchain_runloop",
    ),
    "vercel": SandboxProviderMetadata(
        name="vercel",
        working_dir="/vercel/sandbox",
        install=SandboxInstallHint(kind="extra", name="vercel"),
        supports_sandbox_id=True,
        supports_snapshot_name=False,
        backend_module="langchain_vercel_sandbox",
    ),
}


def _load_class(class_path: str) -> type:
    if ":" not in class_path:
        msg = f"Invalid class_path '{class_path}': must be in module.path:ClassName format"
        raise ValueError(msg)
    module_path, class_name = class_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name, None)
    if cls is None or not isinstance(cls, type):
        msg = f"Class '{class_name}' not found in module '{module_path}'"
        raise ImportError(msg)
    return cls


def _provider_metadata(provider: SandboxProvider, name: str) -> SandboxProviderMetadata:
    meta = getattr(provider, "metadata", None)
    if isinstance(meta, SandboxProviderMetadata):
        return meta
    return SandboxProviderMetadata(name=name, working_dir="/workspace")


class SandboxRegistry:
    def __init__(
        self,
        *,
        config: SandboxConfig | None = None,
        include_entry_points: bool = True,
    ) -> None:
        self._config = config if config is not None else SandboxConfig.load()
        self._include_entry_points = include_entry_points
        self._entry_points: dict[str, importlib.metadata.EntryPoint] = (
            self._discover_entry_points() if include_entry_points else {}
        )

    @classmethod
    def load(cls, config_path: Path | None = None) -> SandboxRegistry:
        return cls(config=SandboxConfig.load(config_path))

    @staticmethod
    def _discover_entry_points() -> dict[str, importlib.metadata.EntryPoint]:
        found: dict[str, importlib.metadata.EntryPoint] = {}
        try:
            entries = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
        except Exception:
            logger.warning("Failed to discover sandbox entry points", exc_info=True)
            return found
        for entry in entries:
            found[entry.name] = entry
        return found

    @property
    def default(self) -> str | None:
        return self._config.default

    @property
    def config_error(self) -> str | None:
        return self._config.parse_error

    def available_providers(self) -> list[str]:
        names = (
            set(BUILTIN_METADATA)
            | set(self._entry_points)
            | set(self._config.providers)
        )
        return sorted(names)

    def is_available(self, name: str) -> bool:
        return (
            name in self._config.providers
            or name in self._entry_points
            or name in BUILTIN_METADATA
        )

    def get_metadata(self, name: str) -> SandboxProviderMetadata | None:
        config_entry = self._config.providers.get(name)
        if config_entry is not None:
            base = BUILTIN_METADATA.get(name)
            package = config_entry.get("package")
            return SandboxProviderMetadata(
                name=name,
                working_dir=config_entry.get(
                    "working_dir", base.working_dir if base else "/workspace"
                ),
                install=(
                    SandboxInstallHint(kind="package", name=package)
                    if package
                    else (base.install if base else None)
                ),
                supports_sandbox_id=config_entry.get(
                    "supports_sandbox_id",
                    base.supports_sandbox_id if base else True,
                ),
                supports_snapshot_name=config_entry.get(
                    "supports_snapshot_name",
                    base.supports_snapshot_name if base else False,
                ),
                backend_module=base.backend_module if base else None,
            )
        if name in self._entry_points:
            return self.provider_metadata(name)
        if name in BUILTIN_METADATA:
            return BUILTIN_METADATA[name]
        return None

    def get_params(self, name: str) -> dict[str, Any]:
        return self._config.get_params(name)

    def create_provider(self, name: str) -> SandboxProvider:
        config_entry = self._config.providers.get(name)
        if config_entry is not None:
            class_path = config_entry.get("class_path")
            if not class_path:
                msg = f"Sandbox provider '{name}' config is missing 'class_path'"
                raise ValueError(msg)
            return _load_class(class_path)()

        entry = self._entry_points.get(name)
        if entry is not None:
            return entry.load()()

        if name in BUILTIN_METADATA:
            return _create_builtin_provider(name)

        msg = (
            f"Unknown sandbox provider: {name}. "
            f"Available providers: {', '.join(self.available_providers())}"
        )
        raise ValueError(msg)

    def provider_metadata(self, name: str) -> SandboxProviderMetadata:
        if name in self._config.providers or (
            name in BUILTIN_METADATA and name not in self._entry_points
        ):
            meta = self.get_metadata(name)
            if meta is not None:
                return meta
        if name in self._entry_points:
            try:
                provider = self.create_provider(name)
            except Exception:
                logger.debug("Could not instantiate provider %r for metadata", name)
                return SandboxProviderMetadata(name=name, working_dir="/workspace")
            return _provider_metadata(provider, name)
        meta = self.get_metadata(name)
        if meta is None:
            msg = f"Unknown sandbox provider: {name}"
            raise ValueError(msg)
        return meta


def _create_builtin_provider(name: str) -> SandboxProvider:
    from opscode.backend.sandbox import factory

    builders = {
        "agentcore": factory._AgentCoreProvider,
        "daytona": factory._DaytonaProvider,
        "langsmith": factory._LangSmithProvider,
        "modal": factory._ModalProvider,
        "runloop": factory._RunloopProvider,
        "vercel": factory._VercelProvider,
    }
    return builders[name]()
