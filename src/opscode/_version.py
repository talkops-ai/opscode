"""Version information and lightweight constants for ``opscode``."""

from importlib.metadata import version as _pkg_version, PackageNotFoundError

try:
    __version__: str = _pkg_version("talkops-opscode")
except PackageNotFoundError:
    # Fallback for editable installs or running from source without install
    __version__ = "0.0.0-dev"

DOCS_URL = "https://github.com/talkops-ai/opscode"
"""URL for ``opscode`` documentation."""

PYPI_URL = "https://pypi.org/pypi/opscode/json"
"""PyPI JSON API endpoint for version checks."""

CHANGELOG_URL = "https://github.com/talkops-ai/opscode/blob/main/CHANGELOG.md"
"""URL for the full changelog."""

USER_AGENT = f"opscode/{__version__}"
"""User-Agent header sent with external HTTP requests."""
