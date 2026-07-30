from urllib.parse import urlparse
from typing import Any
from dcoder.mcp.providers.base import OAuthProvider, LoginResult

class SlackProvider(OAuthProvider):
    def matches(self, server_url: str) -> bool:
        host = urlparse(server_url).hostname or ""
        return host == "slack.com" or host.endswith(".slack.com")

    def loopback_port(self) -> int:
        return 3118

    async def run_login(
        self,
        *,
        server_name: str,
        server_url: str,
        storage: Any,
        ui: Any,
    ) -> LoginResult:
        return LoginResult(extra_auth_params={})
