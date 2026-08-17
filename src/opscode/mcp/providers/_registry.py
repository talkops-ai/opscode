from opscode.mcp.providers.base import GenericProvider, OAuthProvider
from opscode.mcp.providers.github import GitHubProvider
from opscode.mcp.providers.slack import SlackProvider

_REGISTRY: tuple[OAuthProvider, ...] = (
    SlackProvider(),
    GitHubProvider(),
    GenericProvider(),
)

def resolve_provider(server_url: str) -> OAuthProvider:
    for provider in _REGISTRY:
        if provider.matches(server_url):
            return provider
    raise RuntimeError(f"No MCP OAuth provider matched {server_url!r}")
