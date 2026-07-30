from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from deepagents.backends.protocol import SandboxBackendProtocol


@dataclass(frozen=True)
class SandboxInstallHint:
    kind: Literal["extra", "package"]
    name: str

    def command(self, *, in_app: bool) -> str:
        prefix = "/install" if in_app else "dcoder --install"
        suffix = " --package" if self.kind == "package" else ""
        return f"{prefix} {self.name}{suffix}"


@dataclass(frozen=True)
class SandboxProviderMetadata:
    name: str
    working_dir: str
    install: SandboxInstallHint | None = None
    supports_sandbox_id: bool = True
    supports_snapshot_name: bool = False
    backend_module: str | None = None


class SandboxError(Exception):
    @property
    def original_exc(self) -> BaseException | None:
        return self.__cause__


class SandboxNotFoundError(SandboxError):
    pass


class SandboxProvider(ABC):
    @property
    def metadata(self) -> SandboxProviderMetadata | None:
        return None

    @abstractmethod
    def get_or_create(
        self,
        *,
        sandbox_id: str | None = None,
        **kwargs: Any,
    ) -> SandboxBackendProtocol:
        raise NotImplementedError

    @abstractmethod
    def delete(
        self,
        *,
        sandbox_id: str,
        **kwargs: Any,
    ) -> None:
        raise NotImplementedError

    async def aget_or_create(
        self,
        *,
        sandbox_id: str | None = None,
        **kwargs: Any,
    ) -> SandboxBackendProtocol:
        return await asyncio.to_thread(
            self.get_or_create, sandbox_id=sandbox_id, **kwargs
        )

    async def adelete(
        self,
        *,
        sandbox_id: str,
        **kwargs: Any,
    ) -> None:
        await asyncio.to_thread(self.delete, sandbox_id=sandbox_id, **kwargs)
