"""Data models for plugins in DCoder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from pathlib import Path

JsonObject = dict[str, Any]
JsonValue = Any

MarketplaceSourceType = Literal["directory", "file", "github", "git", "url"]
InstallScope = Literal["user", "project", "local"]
"""Plugin installation scope — matches Claude Code's three-tier model."""
ExternalPluginRepositorySourceType = Literal["github", "git-subdir", "url"]
UnsupportedComponent = Literal["hooks"]


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalMarketplaceSource:
    """Local directory or JSON file used as a marketplace source."""

    source_type: Literal["directory", "file"]
    value: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RepositoryMarketplaceSource:
    """GitHub or Git repository used as a marketplace source."""

    source_type: Literal["github", "git"]
    value: str
    ref: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class UrlMarketplaceSource:
    """Marketplace manifest downloaded from an HTTP URL."""

    source_type: Literal["url"]
    value: str


MarketplaceSource = (
    LocalMarketplaceSource | RepositoryMarketplaceSource | UrlMarketplaceSource
)


@dataclass(frozen=True, slots=True, kw_only=True)
class PluginManifest:
    """Parsed plugin manifest."""

    name: str | None
    version: str | None
    component_paths: dict[str, tuple[Path, ...]]
    inline_mcp: JsonObject
    display_name: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ComponentInventory:
    """Inventory of supported plugin components."""

    skills: tuple[Path, ...] = ()
    mcp_files: tuple[Path, ...] = ()
    agents: tuple[Path, ...] = ()
    commands: tuple[Path, ...] = ()
    unsupported: tuple[UnsupportedComponent, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class PluginInstance:
    """A discovered plugin ready to feed adapters.

    Attributes:
        plugin_id: Stable id in `{name}@{marketplace}` form.
        name: Plugin namespace name.
        marketplace: Parent marketplace used for identity and namespacing.
        version: Version declared by the plugin manifest, if any.
        root: Plugin root directory.
        data_dir: Writable data directory for this plugin.
        manifest: Parsed manifest, if any.
        inventory: Component inventory.
    """

    plugin_id: str
    name: str
    marketplace: str
    version: str | None
    root: Path
    data_dir: Path
    manifest: PluginManifest | None
    inventory: ComponentInventory

    def __post_init__(self) -> None:
        expected = f"{self.name}@{self.marketplace}"
        if self.plugin_id != expected:
            msg = f"Plugin id {self.plugin_id!r} does not match {expected!r}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalPluginSource:
    """A plugin stored relative to its marketplace."""

    source_type: Literal["local"]
    path: str


@dataclass(frozen=True, slots=True, kw_only=True)
class GithubPluginSource:
    """A plugin sourced from a GitHub repository."""

    source_type: Literal["github"]
    repo: str
    ref: str | None = None
    path: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class GitSubdirectoryPluginSource:
    """A plugin sourced from a subdirectory in a Git repository."""

    source_type: Literal["git-subdir"]
    url: str
    ref: str | None = None
    path: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class UrlPluginSource:
    """A plugin sourced from a Git repository URL."""

    source_type: Literal["url"]
    url: str
    ref: str | None = None
    path: str | None = None


PluginSource = (
    LocalPluginSource
    | GithubPluginSource
    | GitSubdirectoryPluginSource
    | UrlPluginSource
)


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketplacePluginEntry:
    """A catalog entry from a marketplace manifest."""

    name: str
    source: PluginSource
    description: str | None = None
    author: str | JsonObject | None = None
    display_name: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PluginMarketplace:
    """A parsed marketplace manifest."""

    name: str
    root: Path
    manifest_path: Path
    metadata: JsonObject
    plugins: tuple[MarketplacePluginEntry, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketplaceRecord:
    """Persisted marketplace source record."""

    name: str
    source_type: MarketplaceSourceType
    source: str
    install_location: str
    ref: str | None = None
    is_project: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class InstalledPluginEntry:
    """Install record for a plugin.

    Matches Claude Code's ``installed_plugins.json`` entry schema.
    Each plugin ID maps to an *array* of entries, one per scope.

    Attributes:
        install_path: Absolute path to the cached plugin root.
        version: Version declared by the plugin manifest, if any.
        scope: Installation scope — ``"user"``, ``"project"``, or ``"local"``.
        project_path: Set when ``scope`` is ``"project"`` or ``"local"``;
            absolute path to the project root this entry belongs to.
        installed_at: ISO 8601 timestamp of initial install.
        last_updated: ISO 8601 timestamp of last update.
        git_commit_sha: Optional commit SHA for the plugin source.
    """

    install_path: str
    version: str | None
    scope: InstallScope = "user"
    project_path: str | None = None
    installed_at: str | None = None
    last_updated: str | None = None
    git_commit_sha: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PluginDiscoveryResult:
    """Result from plugin discovery."""

    plugins: tuple[PluginInstance, ...]
    warnings: tuple[str, ...] = ()


def split_plugin_id(plugin_id: str) -> tuple[str, str]:
    """Split a plugin id in `{plugin}@{marketplace}` form.

    Returns:
        Plugin and marketplace names.

    Raises:
        ValueError: If either part is missing.
    """
    if "@" not in plugin_id:
        msg = f"Invalid plugin id {plugin_id!r}; expected name@marketplace"
        raise ValueError(msg)
    plugin, marketplace = plugin_id.rsplit("@", 1)
    if not plugin or not marketplace:
        msg = f"Invalid plugin id {plugin_id!r}; expected name@marketplace"
        raise ValueError(msg)
    return plugin, marketplace
