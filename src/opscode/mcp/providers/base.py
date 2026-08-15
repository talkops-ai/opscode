from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class LoginResult:
    completed: bool = False
    extra_auth_params: dict[str, str] = field(default_factory=dict)

class OAuthProvider(ABC):
    @abstractmethod
    def matches(self, server_url: str) -> bool:
        pass

    def supports_loopback_callback(self) -> bool:
        return True

    def loopback_port(self) -> int | None:
        return None

    async def run_login(
        self,
        *,
        server_name: str,
        server_url: str,
        storage: Any,
        ui: Any,
    ) -> LoginResult:
        return LoginResult()

class GenericProvider(OAuthProvider):
    def matches(self, server_url: str) -> bool:
        return True
