"""Canonical manifest and resolver for every user-tunable config option.

This module is the single source of truth for the configuration *surface*: the
set of options, their types, typed defaults, env-var names, ``config.toml``
locations, and ``Settings`` dataclass field mappings. The ``/config`` command
and the ``ConfigManagerScreen`` widget iterate ``get_config_options()`` to
dynamically discover what settings exist — so adding a new option is just
adding one ``ConfigOption`` entry here.

``resolve_scalar`` is the shared resolution engine: env var (with ``OPSCODE_``
prefix priority) → ``config.toml`` → typed default, returning both the
effective value and its source label.
"""

from __future__ import annotations

import dataclasses
import logging
import os
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)

# ── Constants — re-exported from paths.py (single source of truth) ───
# These re-exports maintain backward compatibility for existing imports.

from opscode.config.paths import (  # noqa: F401
    ENV_PREFIX,
    DEFAULT_AGENT_NAME,
    DATA_DIR as DEFAULT_CONFIG_DIR,
    CONFIG_PATH as DEFAULT_CONFIG_PATH,
    DOTENV_DENIED_ENV_KEYS,
    PROJECT_ROOT_MARKERS,
    RELOADABLE_FIELDS,
    DEVOPS_PRESERVE_ENV_VARS,
)

# ── OptionKind ───────────────────────────────────────────


class OptionKind(Enum):
    """How an option's raw env/TOML value is coerced to a typed value."""

    BOOL = "bool"
    """Truthy (``true``/``1``/``yes``) or falsy (``false``/``0``/``no``)."""

    INT = "int"

    FLOAT = "float"

    STR = "str"

    CHOICE = "choice"
    """Cycles through a fixed ``choices`` tuple."""

    PATH = "path"
    """Single filesystem path."""

    SHELL_LIST = "shell_list"
    """Comma-separated command list."""

    SECRET = "secret"
    """Masked on display; never logged in full."""


_KIND_TYPE_LABEL: dict[OptionKind, str] = {
    OptionKind.BOOL: "bool",
    OptionKind.INT: "int",
    OptionKind.FLOAT: "float",
    OptionKind.STR: "str",
    OptionKind.CHOICE: "choice",
    OptionKind.PATH: "path",
    OptionKind.SHELL_LIST: "list[str]",
    OptionKind.SECRET: "secret",
}

# Fail at import (and in the test suite) if a kind is missing.
if _KIND_TYPE_LABEL.keys() != set(OptionKind):
    msg = "_KIND_TYPE_LABEL is missing an OptionKind entry"
    raise RuntimeError(msg)


# ── ConfigOption ─────────────────────────────────────────


@dataclass(frozen=True)
class ConfigOption:
    """One user-tunable configuration option and where it can be set.

    The manifest screen uses ``group`` for visual sections and ``summary`` as
    the display label.  ``settings_field`` links back to the ``Settings``
    dataclass; when ``None``, the option is env-var-only or display-only.
    """

    key: str
    """Canonical dotted identifier used by ``/config get`` and as a display key."""

    group: str
    """Human-readable grouping for the config UI."""

    summary: str
    """One-line description of what the option controls."""

    kind: OptionKind
    """How env/TOML values are coerced to a typed value."""

    default: Any = None
    """Typed default value, or ``None`` when there is no static default."""

    env_var: str | None = None
    """Primary environment variable name the loader reads, or ``None``."""

    toml_keys: tuple[str, ...] | None = None
    """Section/key path within ``config.toml``, or ``None``."""

    settings_field: str | None = None
    """Name of the ``Settings`` attribute this option backs, or ``None``."""

    redacted: bool = False
    """Whether ``/config`` masks the value (shows only set/not-set)."""

    choices: tuple[str, ...] | None = None
    """Valid values when ``kind`` is ``CHOICE``."""

    @property
    def type_label(self) -> str:
        """Human-readable type label derived from ``kind``."""
        return _KIND_TYPE_LABEL[self.kind]

    @property
    def toml_path(self) -> str | None:
        """Render ``toml_keys`` as a ``[section].key`` display string."""
        if not self.toml_keys:
            return None
        *sections, leaf = self.toml_keys
        if not sections:
            return leaf
        return f"[{'.'.join(sections)}].{leaf}"


# ── Resolution ───────────────────────────────────────────


def load_config_toml() -> dict[str, Any]:
    """Load ``~/.opscode/config.toml``.

    Returns:
        The parsed config mapping, or ``{}`` when the file is absent or invalid.
    """
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

    try:
        with DEFAULT_CONFIG_PATH.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, Exception) as exc:
        logger.warning(
            "Could not read config from %s; using defaults (%s)",
            DEFAULT_CONFIG_PATH,
            exc,
        )
        return {}


def _toml_lookup(data: dict[str, Any], keys: tuple[str, ...]) -> tuple[bool, Any]:
    """Navigate nested ``keys`` in ``data``.

    Returns:
        ``(found, value)`` where ``found`` is ``False`` if any key is missing.
    """
    node: Any = data
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return False, None
        node = node[key]
    return True, node


def _coerce_env(option: ConfigOption, raw: str) -> Any:
    """Coerce a raw environment-variable string by the option's kind.

    Returns the typed value, or ``None`` when the raw value cannot be coerced.
    """
    kind = option.kind
    if kind == OptionKind.BOOL:
        low = raw.strip().lower()
        if low in ("true", "1", "yes", "on"):
            return True
        if low in ("false", "0", "no", "off"):
            return False
        return None
    if kind == OptionKind.INT:
        try:
            return int(raw.strip())
        except ValueError:
            return None
    if kind == OptionKind.FLOAT:
        try:
            return float(raw.strip())
        except ValueError:
            return None
    if kind in (OptionKind.STR, OptionKind.CHOICE, OptionKind.SECRET):
        return raw
    if kind == OptionKind.SHELL_LIST:
        return [cmd.strip() for cmd in raw.split(",") if cmd.strip()]
    if kind == OptionKind.PATH:
        return Path(raw).expanduser()
    return raw


def _coerce_toml(option: ConfigOption, raw: Any) -> Any:
    """Coerce a raw TOML value by the option's kind.

    Returns the typed value, or ``None`` when the raw value has the wrong shape.
    """
    kind = option.kind
    if kind == OptionKind.BOOL:
        return raw if isinstance(raw, bool) else None
    if kind == OptionKind.INT:
        return raw if isinstance(raw, int) and not isinstance(raw, bool) else None
    if kind == OptionKind.FLOAT:
        return float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None
    if kind in (OptionKind.STR, OptionKind.CHOICE, OptionKind.SECRET):
        return raw if isinstance(raw, str) else None
    if kind == OptionKind.SHELL_LIST:
        if isinstance(raw, str):
            return [cmd.strip() for cmd in raw.split(",") if cmd.strip()]
        if isinstance(raw, list):
            return [str(item) for item in raw if item]
        return None
    if kind == OptionKind.PATH:
        return Path(raw).expanduser() if isinstance(raw, str) else None
    return None


def resolve_scalar(
    option: ConfigOption,
    *,
    settings: Any | None = None,
    toml_data: dict[str, Any] | None = None,
) -> tuple[Any, str]:
    """Resolve an option against Settings → env → config.toml → default.

    Args:
        option: The option to resolve.
        settings: A ``Settings`` instance (checked first for live runtime values).
        toml_data: Parsed ``config.toml`` mapping. Loaded lazily if ``None``.

    Returns:
        ``(value, source)`` where ``source`` is one of ``"settings"``, ``"env (NAME)"``,
        ``"config.toml"``, or ``"default"``.
    """
    # 1. Live Settings field (highest priority — reflects runtime mutations)
    if settings is not None and option.settings_field:
        val = getattr(settings, option.settings_field, None)
        if val is not None:
            return val, "settings"

    # 2. Environment variable (with OPSCODE_ prefix priority)
    if option.env_var:
        prefixed = f"{ENV_PREFIX}{option.env_var}"
        for name in (prefixed, option.env_var):
            raw = os.environ.get(name)
            if raw is not None and raw:
                coerced = _coerce_env(option, raw)
                if coerced is not None:
                    return coerced, f"env ({name})"

    # 3. config.toml
    if option.toml_keys:
        if toml_data is None:
            toml_data = load_config_toml()
        found, raw = _toml_lookup(toml_data, option.toml_keys)
        if found:
            coerced = _coerce_toml(option, raw)
            if coerced is not None:
                return coerced, "config.toml"

    # 4. Typed default
    return option.default, "default"


# ── Credential Auto-Discovery ────────────────────────────

_SECRET_NAME_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD")

# Map of env-var name → Settings field name for known credentials.
_CREDENTIAL_SETTINGS_FIELDS: dict[str, str] = {
    "OPENAI_API_KEY": "openai_api_key",
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "GOOGLE_API_KEY": "google_api_key",
    "GROQ_API_KEY": "groq_api_key",
    "DEEPSEEK_API_KEY": "deepseek_api_key",
    "TAVILY_API_KEY": "tavily_api_key",
}

# Provider names for display, keyed by env var.
_CREDENTIAL_PROVIDERS: dict[str, str] = {
    "OPENAI_API_KEY": "openai",
    "ANTHROPIC_API_KEY": "anthropic",
    "GOOGLE_API_KEY": "google",
    "GROQ_API_KEY": "groq",
    "DEEPSEEK_API_KEY": "deepseek",
    "TAVILY_API_KEY": "tavily",
}


def _credential_options() -> tuple[ConfigOption, ...]:
    """Build credential options from the known provider/key registries.

    Auto-generates one ``ConfigOption`` per credential so adding a new provider
    to ``_CREDENTIAL_SETTINGS_FIELDS`` surfaces it in ``/config`` automatically.
    """
    options: list[ConfigOption] = []
    for env_var, field_name in sorted(_CREDENTIAL_SETTINGS_FIELDS.items()):
        provider = _CREDENTIAL_PROVIDERS.get(env_var, field_name.replace("_api_key", ""))
        options.append(
            ConfigOption(
                key=f"credentials.{provider}",
                group="Credentials",
                summary=f"{provider.title()} API Key",
                kind=OptionKind.SECRET,
                env_var=env_var,
                settings_field=field_name,
                redacted=True,
            )
        )
    return tuple(options)


# ── Static Option Definitions ────────────────────────────

_STATIC_OPTIONS: tuple[ConfigOption, ...] = (
    # --- Models --------------------------------------------------------
    ConfigOption(
        key="models.name",
        group="Models",
        summary="Active model name",
        kind=OptionKind.STR,
        toml_keys=("model", "default"),
        settings_field="model_name",
    ),
    ConfigOption(
        key="models.provider",
        group="Models",
        summary="Active model provider",
        kind=OptionKind.STR,
        settings_field="model_provider",
    ),
    ConfigOption(
        key="models.reasoning_effort",
        group="Models",
        summary="Reasoning effort level",
        kind=OptionKind.CHOICE,
        default="medium",
        choices=("low", "medium", "high"),
        toml_keys=("model", "reasoning_effort"),
        settings_field="reasoning_effort",
    ),
    ConfigOption(
        key="models.context_limit",
        group="Models",
        summary="Model context window limit",
        kind=OptionKind.INT,
        settings_field="model_context_limit",
    ),
    # --- Display / UI --------------------------------------------------
    ConfigOption(
        key="display.theme",
        group="Display",
        summary="Active color theme",
        kind=OptionKind.STR,
        default="dark",
        env_var="OPSCODE_THEME",
        toml_keys=("ui", "theme"),
        settings_field="theme",
    ),
    ConfigOption(
        key="display.show_scrollbar",
        group="Display",
        summary="Show vertical scrollbar in chat area",
        kind=OptionKind.BOOL,
        default=False,
        toml_keys=("ui", "show_scrollbar"),
        settings_field="show_scrollbar",
    ),
    ConfigOption(
        key="display.show_timestamps",
        group="Display",
        summary="Show timestamps on messages",
        kind=OptionKind.BOOL,
        default=True,
        toml_keys=("ui", "show_timestamps"),
        settings_field="show_timestamps",
    ),
    ConfigOption(
        key="display.auto_scroll",
        group="Display",
        summary="Auto-scroll to newest messages",
        kind=OptionKind.BOOL,
        default=True,
        toml_keys=("ui", "auto_scroll"),
        settings_field="auto_scroll",
    ),
    ConfigOption(
        key="display.notifications_enabled",
        group="Display",
        summary="Enable desktop notifications",
        kind=OptionKind.BOOL,
        default=True,
        toml_keys=("ui", "notifications"),
        settings_field="notifications_enabled",
    ),
    ConfigOption(
        key="display.show_turn_duration",
        group="Display",
        summary="Show agent turn duration",
        kind=OptionKind.BOOL,
        default=True,
        toml_keys=("ui", "show_turn_duration"),
        settings_field="show_turn_duration",
    ),
    ConfigOption(
        key="display.verbose_output",
        group="Display",
        summary="Enable verbose output mode",
        kind=OptionKind.BOOL,
        default=False,
        env_var="OPSCODE_VERBOSE",
        toml_keys=("ui", "verbose"),
        settings_field="verbose_output",
    ),
    ConfigOption(
        key="display.auto_compact",
        group="Display",
        summary="Auto-compact conversation history",
        kind=OptionKind.BOOL,
        default=False,
        toml_keys=("ui", "auto_compact"),
        settings_field="auto_compact",
    ),
    # --- Tools / Features ----------------------------------------------
    ConfigOption(
        key="shell.allow_list",
        group="Tools",
        summary="Shell commands allowed without approval",
        kind=OptionKind.SHELL_LIST,
        env_var="SHELL_ALLOW_LIST",
        settings_field="shell_allow_list",
    ),
    ConfigOption(
        key="skills.extra_dirs",
        group="Tools",
        summary="Additional skill directories",
        kind=OptionKind.STR,
        env_var="OPSCODE_EXTRA_SKILLS_DIRS",
        settings_field="extra_skills_dirs",
    ),
    # --- Interpreter ---------------------------------------------------
    ConfigOption(
        key="interpreter.enabled",
        group="Interpreter",
        summary="Enable JavaScript interpreter (PTC)",
        kind=OptionKind.BOOL,
        default=False,
        toml_keys=("interpreter", "enable_interpreter"),
        settings_field="enable_interpreter",
    ),
    ConfigOption(
        key="interpreter.ptc",
        group="Interpreter",
        summary="Programmatic tool-calling mode",
        kind=OptionKind.STR,
        toml_keys=("interpreter", "ptc"),
        settings_field="interpreter_ptc",
    ),
    ConfigOption(
        key="interpreter.ptc_acknowledge_unsafe",
        group="Interpreter",
        summary="Acknowledge unsafe PTC exposure",
        kind=OptionKind.BOOL,
        default=False,
        toml_keys=("interpreter", "ptc_acknowledge_unsafe"),
        settings_field="interpreter_ptc_acknowledge_unsafe",
    ),
    # --- Project -------------------------------------------------------
    ConfigOption(
        key="project.root",
        group="Project",
        summary="Project root directory",
        kind=OptionKind.PATH,
        settings_field="project_root",
    ),
    # --- Permissions ---------------------------------------------------
    ConfigOption(
        key="permissions.shell_read",
        group="Permissions",
        summary="Allow non-mutating shell commands",
        kind=OptionKind.BOOL,
        default=True,
    ),
    ConfigOption(
        key="permissions.shell_write",
        group="Permissions",
        summary="Allow mutating shell commands",
        kind=OptionKind.BOOL,
        default=False,
    ),
    ConfigOption(
        key="permissions.file_read",
        group="Permissions",
        summary="Allow file read operations",
        kind=OptionKind.BOOL,
        default=True,
    ),
    ConfigOption(
        key="permissions.file_write",
        group="Permissions",
        summary="Allow file write operations",
        kind=OptionKind.BOOL,
        default=False,
    ),
    ConfigOption(
        key="permissions.infra_plan",
        group="Permissions",
        summary="Allow infrastructure plan operations",
        kind=OptionKind.BOOL,
        default=False,
    ),
    ConfigOption(
        key="permissions.infra_apply",
        group="Permissions",
        summary="Allow infrastructure apply operations",
        kind=OptionKind.BOOL,
        default=False,
    ),
)


# ── Public API ───────────────────────────────────────────


@lru_cache(maxsize=1)
def get_config_options() -> tuple[ConfigOption, ...]:
    """Return every option, credentials-first then by domain group.

    Cached: credential options are generated once from the registry on first
    call.  The cache assumes the registries are immutable module constants.
    """
    return _credential_options() + _STATIC_OPTIONS


def get_option(key: str) -> ConfigOption | None:
    """Return the manifest entry for ``key``, or ``None`` when unknown."""
    return _options_by_key().get(key)


def option_keys() -> tuple[str, ...]:
    """Return every manifest key in definition order."""
    return tuple(opt.key for opt in get_config_options())


@lru_cache(maxsize=1)
def _options_by_key() -> dict[str, ConfigOption]:
    return {opt.key: opt for opt in get_config_options()}


def iter_groups(options: Iterable[ConfigOption] | None = None) -> list[str]:
    """Return group names from ``options`` in first-seen order."""
    if options is None:
        options = get_config_options()
    groups: list[str] = []
    for opt in options:
        if opt.group not in groups:
            groups.append(opt.group)
    return groups
