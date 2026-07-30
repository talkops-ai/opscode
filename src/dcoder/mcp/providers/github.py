from urllib.parse import urlparse
from typing import Any
from dcoder.mcp.providers.base import OAuthProvider, LoginResult

class GitHubProvider(OAuthProvider):
    def matches(self, server_url: str) -> bool:
        return (urlparse(server_url).hostname or "") == "api.githubcopilot.com"

    async def run_login(
        self,
        *,
        server_name: str,
        server_url: str,
        storage: Any,
        ui: Any,
    ) -> LoginResult:
        return LoginResult(completed=True)
