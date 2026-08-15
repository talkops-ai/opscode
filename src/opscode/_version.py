"""Version information and lightweight constants for ``opscode``."""

# Keep the ``x-release-please-version`` annotation — release-please uses it to
# bump ``__version__`` in sync with ``pyproject.toml`` on every release PR.
__version__ = "0.1.0"  # x-release-please-version

DOCS_URL = "https://github.com/talkops-ai/opscode"
"""URL for ``opscode`` documentation."""

PYPI_URL = "https://pypi.org/pypi/opscode/json"
"""PyPI JSON API endpoint for version checks."""

CHANGELOG_URL = "https://github.com/talkops-ai/opscode/blob/main/CHANGELOG.md"
"""URL for the full changelog."""

USER_AGENT = f"opscode/{__version__}"
"""User-Agent header sent with external HTTP requests."""
