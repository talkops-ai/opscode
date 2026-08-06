"""Global settings, environment detection, and bootstrap for dcoder."""

import logging
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dcoder.config import paths
from dcoder.config.manifest import (
    ENV_PREFIX,
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_PATH,
    DOTENV_DENIED_ENV_KEYS,
    PROJECT_ROOT_MARKERS,
    RELOADABLE_FIELDS,
)

logger = logging.getLogger("dcoder")

# ── Bootstrap State ──────────────────────────────────────

@dataclass
class _BootstrapState:
    done: bool = False
    start_path: Path | None = None

_bootstrap_state = _BootstrapState()
_bootstrap_lock = threading.Lock()

def _ensure_bootstrap() -> None:
    """One-time bootstrap: dotenv loading.
    
    Idempotent and thread-safe. Called by _get_settings().
    Flag set in `finally` to prevent infinite retries on partial failure.
    """
    if _bootstrap_state.done:
        return
    with _bootstrap_lock:
        if _bootstrap_state.done:
            return
        try:
            _bootstrap_state.start_path = Path.cwd()
            _load_dotenv(start_path=_bootstrap_state.start_path)
        except Exception:
            logger.exception("Bootstrap failed; proceeding with env as-is.")
        finally:
            _bootstrap_state.done = True

# ── Env-Var Resolution ───────────────────────────────────

def resolve_env_var(name: str) -> str | None:
    """Resolve env var with DCODER_ prefix priority.
    
    1. Check DCODER_{name} (takes precedence)
    2. Check plain {name}
    3. Return None (empty string treated as unset)
    """
    _ensure_bootstrap()
    prefixed = f"{ENV_PREFIX}{name}"
    value = os.environ.get(prefixed)
    if value is not None:
        return value or None
    value = os.environ.get(name)
    return value or None

def _resolve_env_var_from(env: dict[str, str], name: str) -> str | None:
    """Helper to resolve env vars from a specific dictionary mapping."""
    prefixed = f"{ENV_PREFIX}{name}"
    value = env.get(prefixed)
    if value is not None:
        return value or None
    value = env.get(name)
    return value or None

# ── Dotenv Loading ───────────────────────────────────────

def _load_dotenv(*, start_path: Path | None = None, refresh_loaded: bool = False) -> None:
    """Load .env files: project-level (walk-up), then ~/.dcoder/.env.
    
    Security: Keys in DOTENV_DENIED_ENV_KEYS are stripped after loading.
    """
    from dotenv import dotenv_values
    
    # 1. Locate project .env
    search = start_path or Path.cwd()
    project_env: Path | None = None
    while search != search.parent:
        candidate = search / ".env"
        if candidate.is_file():
            project_env = candidate
            break
        search = search.parent
        
    loaded_vals: dict[str, str | None] = {}
    
    # 1. Global ~/.dcoder/.env (individual provider keys live here)
    global_env = paths.GLOBAL_ENV_PATH
    if global_env.is_file():
        loaded_vals.update(dotenv_values(global_env))
        
    # 2. Project/CWD .env (higher priority, overwrites global)
    if project_env:
        loaded_vals.update(dotenv_values(project_env))
        
    # Filter out denied keys
    for key in DOTENV_DENIED_ENV_KEYS:
        if key in loaded_vals:
            logger.warning("Denied .env key in dotenv file: %s", key)
            loaded_vals.pop(key, None)
            
    # Apply to os.environ
    for k, v in loaded_vals.items():
        if v is not None:
            if refresh_loaded or k not in os.environ:
                os.environ[k] = v
                
    # Re-apply log configuration (in case .env enabled debug or changed level)
    # The initial install ran at package import, but .env overrides it here.
    from dcoder._debug import configure_debug_logging
    configure_debug_logging(logging.getLogger("dcoder"))

# ── Project Root Detection ───────────────────────────────

def _find_project_root(start_path: Path | None = None) -> Path | None:
    """Locate the project root by searching up for markers."""
    current = Path(start_path or Path.cwd()).expanduser().resolve()
    for directory in (current, *current.parents):
        for marker in PROJECT_ROOT_MARKERS:
            if (directory / marker).exists():
                return directory
    return None

def parse_shell_allow_list(value: str | None) -> list[str] | None:
    """Parse comma-separated list of allowed shell commands."""
    if value is None:
        return None
    if not value.strip():
        return []
    return [cmd.strip() for cmd in value.split(",") if cmd.strip()]

# ── Settings Dataclass ───────────────────────────────────

@dataclass
class Settings:
    # Provider credentials
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    groq_api_key: str | None = None
    deepseek_api_key: str | None = None
    tavily_api_key: str | None = None
    
    # Runtime model state (mutated by ModelResult.apply_to_settings)
    model_name: str | None = None
    model_provider: str | None = None
    model_context_limit: int | None = None
    model_unsupported_modalities: frozenset[str] = field(default_factory=frozenset)
    reasoning_effort: str | None = None
    
    # Assistant / Agent ID
    assistant_id: str | None = None

    # Project
    project_root: Path | None = None
    
    # Shell
    shell_allow_list: list[str] | None = None
    
    # Skills
    extra_skills_dirs: list[Path] | None = None

    # Interpreter
    enable_interpreter: bool = True
    interpreter_ptc: str | list[str] | None = "safe"
    interpreter_ptc_acknowledge_unsafe: bool = False
    
    # Telemetry / Tracing
    user_langchain_project: str | None = "dcoder"

    # Display / UI (curated settings surfaced in /config)
    theme: str = "dark"
    show_scrollbar: bool = False
    show_timestamps: bool = True
    auto_scroll: bool = True
    notifications_enabled: bool = True
    verbose_output: bool = False
    show_turn_duration: bool = True
    auto_compact: bool = False
    
    @property
    def has_openai(self) -> bool:
        return self.openai_api_key is not None
        
    @property
    def has_anthropic(self) -> bool:
        return self.anthropic_api_key is not None
        
    @property
    def has_tavily(self) -> bool:
        return self.tavily_api_key is not None
        
    @property
    def user_dcoder_dir(self) -> Path:
        return paths.DATA_DIR
        
    @property
    def config_path(self) -> Path:
        """Return the path to the active config file."""
        return paths.CONFIG_PATH

    def to_display_dict(self) -> dict[str, str]:
        """Return all non-None fields as a display-friendly ordered dict.
        
        Groups: credentials → model → project → shell → interpreter.
        Values are stringified. None values are excluded.
        """
        import dataclasses
        result = {}
        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            if value is not None:
                result[f.name] = str(value)
        return result

    def set_field(self, key: str, value: str) -> tuple[bool, str]:
        """Set a settings field by name with basic type coercion.
        
        Args:
            key: Field name (must exist in Settings dataclass).
            value: String value to set.
            
        Returns:
            Tuple of (success: bool, message: str).
        """
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(self)}
        if key not in field_names:
            return False, f"Unknown setting: {key}. Available: {', '.join(sorted(field_names))}"
        
        field_obj = next(f for f in dataclasses.fields(self) if f.name == key)
        
        # Type coercion
        type_str = field_obj.type if isinstance(field_obj.type, str) else getattr(field_obj.type, "__name__", str(field_obj.type))
        try:
            if type_str in ("bool", "bool | None"):
                coerced: Any = value.lower() in ("true", "1", "yes")
            elif type_str in ("int", "int | None"):
                coerced = int(value)
            elif type_str in ("Path | None", "Path"):
                coerced = Path(value)
            else:
                coerced = value
            setattr(self, key, coerced)
            return True, f"Set {key} = {value}"
        except (ValueError, TypeError) as e:
            return False, f"Invalid value for {key}: {e}"

    def reset_field(self, key: str) -> tuple[bool, str]:
        """Reset a settings field to its default value.
        
        Returns:
            Tuple of (success: bool, message: str).
        """
        import dataclasses
        field_names = {f.name: f for f in dataclasses.fields(self)}
        if key not in field_names:
            return False, f"Unknown setting: {key}"
        
        f = field_names[key]
        default = f.default if f.default is not dataclasses.MISSING else None
        setattr(self, key, default)
        return True, f"Reset {key} to default"

        
    @classmethod
    def from_environment(cls, *, start_path: Path | None = None) -> "Settings":
        """Create settings by detecting the current environment."""
        openai_key = resolve_env_var("OPENAI_API_KEY")
        anthropic_key = resolve_env_var("ANTHROPIC_API_KEY")
        google_key = resolve_env_var("GOOGLE_API_KEY")
        groq_key = resolve_env_var("GROQ_API_KEY")
        deepseek_key = resolve_env_var("DEEPSEEK_API_KEY")
        tavily_key = resolve_env_var("TAVILY_API_KEY")
        
        project_root = _find_project_root(start_path)
        shell_allow_list_str = os.environ.get(f"{ENV_PREFIX}SHELL_ALLOW_LIST") or os.environ.get("SHELL_ALLOW_LIST")
        shell_allow_list = parse_shell_allow_list(shell_allow_list_str)
        
        return cls(
            openai_api_key=openai_key,
            anthropic_api_key=anthropic_key,
            google_api_key=google_key,
            groq_api_key=groq_key,
            deepseek_api_key=deepseek_key,
            tavily_api_key=tavily_key,
            project_root=project_root,
            shell_allow_list=shell_allow_list,
        )
        
    def reload_from_environment(self, *, start_path: Path | None = None) -> list[str]:
        """Hot-reload reloadable settings (API keys, project root, etc.)."""
        _load_dotenv(start_path=start_path, refresh_loaded=True)
        
        previous = {field_name: getattr(self, field_name) for field_name in RELOADABLE_FIELDS}
        
        env_map = dict(os.environ)
        refreshed: dict[str, Any] = {
            "openai_api_key": _resolve_env_var_from(env_map, "OPENAI_API_KEY"),
            "anthropic_api_key": _resolve_env_var_from(env_map, "ANTHROPIC_API_KEY"),
            "google_api_key": _resolve_env_var_from(env_map, "GOOGLE_API_KEY"),
            "groq_api_key": _resolve_env_var_from(env_map, "GROQ_API_KEY"),
            "deepseek_api_key": _resolve_env_var_from(env_map, "DEEPSEEK_API_KEY"),
            "project_root": _find_project_root(start_path),
            "shell_allow_list": parse_shell_allow_list(
                env_map.get(f"{ENV_PREFIX}SHELL_ALLOW_LIST") or env_map.get("SHELL_ALLOW_LIST")
            )
        }
        
        changes = []
        for field_name in RELOADABLE_FIELDS:
            old_val = previous[field_name]
            new_val = refreshed.get(field_name)
            if old_val != new_val:
                setattr(self, field_name, new_val)
                # mask API keys in logged changes
                if "api_key" in field_name:
                    old_disp = "set" if old_val else "unset"
                    new_disp = "set" if new_val else "unset"
                else:
                    old_disp = str(old_val)
                    new_disp = str(new_val)
                changes.append(f"{field_name}: {old_disp} -> {new_disp}")
                
        return changes

    def preview_reload_from_environment(self, *, start_path: Path | None = None) -> list[str]:
        """Preview settings changes (stubbed for parity)."""
        return []
        
    # ── Path Helpers ─────────────────────────────────────
    
    @staticmethod
    def _is_valid_agent_name(agent_name: str) -> bool:
        if not agent_name or not agent_name.strip():
            return False
        return bool(re.match(r"^[a-zA-Z0-9_\-\s]+$", agent_name))
        
    def get_agent_dir(self, agent_name: str) -> Path:
        return paths.agent_dir(agent_name)
        
    def ensure_config_dir(self) -> Path:
        return paths.ensure_data_dir()
        
    def ensure_state_dir(self) -> Path:
        return paths.ensure_state_dir()
        
    def ensure_agent_dir(self, agent_name: str) -> Path:
        return paths.ensure_agent_dir(agent_name)
        
    def get_user_skills_dir(self, agent_name: str | None = None) -> Path:
        name = agent_name or self.assistant_id or paths.DEFAULT_AGENT_NAME
        return paths.user_skills_dir(name)

    def ensure_user_skills_dir(self, agent_name: str | None = None) -> Path:
        d = self.get_user_skills_dir(agent_name)
        d.mkdir(parents=True, exist_ok=True)
        return d
        
    def get_project_skills_dir(self) -> Path | None:
        if not self.project_root:
            return None
        return paths.project_skills_dir(self.project_root)
        
    def ensure_project_skills_dir(self) -> Path | None:
        if not self.project_root:
            return None
        d = self.get_project_skills_dir()
        if d:
            d.mkdir(parents=True, exist_ok=True)
        return d
        
    def get_user_agents_dir(self, agent_name: str | None = None) -> Path:
        name = agent_name or self.assistant_id or paths.DEFAULT_AGENT_NAME
        return paths.user_agents_dir(name)
        
    def get_project_agents_dir(self) -> Path | None:
        if not self.project_root:
            return None
        return paths.project_agents_dir(self.project_root)
        
    def get_user_agent_md_path(self, agent_name: str | None = None) -> Path:
        name = agent_name or self.assistant_id or paths.DEFAULT_AGENT_NAME
        return paths.user_agent_md(name)
        
    def get_project_agent_md_path(self) -> list[Path]:
        if not self.project_root:
            return []
        result = []
        for candidate in paths.project_agent_md_paths(self.project_root):
            if candidate.is_file():
                result.append(candidate)
        return result

    def get_extra_skills_dirs(self) -> list[Path]:
        return self.extra_skills_dirs or []

# ── Lazy Singleton ───────────────────────────────────────

_singleton_lock = threading.Lock()

def _get_settings() -> Settings:
    cached = globals().get("settings")
    if cached is not None:
        return cached
    with _singleton_lock:
        cached = globals().get("settings")
        if cached is not None:
            return cached
        _ensure_bootstrap()
        inst = Settings.from_environment(start_path=_bootstrap_state.start_path)
        globals()["settings"] = inst
        return inst

def __getattr__(name: str):
    if name == "settings":
        return _get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# ── Glyphs & Charset Mode ───────────────────────────────

from enum import StrEnum
import sys

class CharsetMode(StrEnum):
    UNICODE = "unicode"
    ASCII = "ascii"
    AUTO = "auto"

@dataclass(frozen=True)
class Glyphs:
    tool_prefix: str
    ellipsis: str
    checkmark: str
    error: str
    circle_empty: str
    circle_filled: str
    output_prefix: str
    spinner_frames: tuple[str, ...]
    pause: str
    newline: str
    warning: str
    question: str
    hourglass: str
    retry: str
    arrow_up: str
    arrow_down: str
    bullet: str
    cursor: str
    disclosure_collapsed: str
    disclosure_expanded: str
    box_vertical: str
    box_horizontal: str
    box_double_horizontal: str
    gutter_bar: str
    git_branch: str

UNICODE_GLYPHS = Glyphs(
    tool_prefix="⏺",
    ellipsis="…",
    checkmark="✓",
    error="✗",
    circle_empty="○",
    circle_filled="●",
    output_prefix="⎿",
    spinner_frames=("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"),
    pause="⏸",
    newline="⏎",
    warning="⚠",
    question="?",
    hourglass="⏳",
    retry="↻",
    arrow_up="↑",
    arrow_down="↓",
    bullet="•",
    cursor="›",
    disclosure_collapsed="▸",
    disclosure_expanded="▾",
    box_vertical="│",
    box_horizontal="─",
    box_double_horizontal="═",
    gutter_bar="▌",
    git_branch="↗",
)

ASCII_GLYPHS = Glyphs(
    tool_prefix="(*)",
    ellipsis="...",
    checkmark="[OK]",
    error="[X]",
    circle_empty="[ ]",
    circle_filled="[*]",
    output_prefix="L",
    spinner_frames=("(-)", "(\\)", "(|)", "(/)"),
    pause="||",
    newline="\\n",
    warning="[!]",
    question="[?]",
    hourglass="[~]",
    retry="[R]",
    arrow_up="^",
    arrow_down="v",
    bullet="-",
    cursor=">",
    disclosure_collapsed=">",
    disclosure_expanded="v",
    box_vertical="|",
    box_horizontal="-",
    box_double_horizontal="=",
    gutter_bar="|",
    git_branch="git:",
)

_glyphs_cache: Glyphs | None = None
_charset_mode_cache: CharsetMode | None = None

def _compute_charset_mode() -> CharsetMode:
    env_mode = (resolve_env_var("UI_CHARSET_MODE") or "auto").lower()
    if env_mode == "unicode":
        return CharsetMode.UNICODE
    if env_mode == "ascii":
        return CharsetMode.ASCII
    encoding = getattr(sys.stdout, "encoding", "") or ""
    if "utf" in encoding.lower():
        return CharsetMode.UNICODE
    lang = os.environ.get("LANG", "") or os.environ.get("LC_ALL", "")
    if "utf" in lang.lower():
        return CharsetMode.UNICODE
    return CharsetMode.ASCII

def _detect_charset_mode() -> CharsetMode:
    global _charset_mode_cache
    if _charset_mode_cache is not None:
        return _charset_mode_cache
    _charset_mode_cache = _compute_charset_mode()
    return _charset_mode_cache

def get_glyphs() -> Glyphs:
    global _glyphs_cache
    if _glyphs_cache is not None:
        return _glyphs_cache
    mode = _detect_charset_mode()
    _glyphs_cache = ASCII_GLYPHS if mode == CharsetMode.ASCII else UNICODE_GLYPHS
    return _glyphs_cache

def is_ascii_mode() -> bool:
    return _detect_charset_mode() == CharsetMode.ASCII

def newline_shortcut() -> str:
    """Return terminal-appropriate label for newline shortcut (Option+Enter on Mac, Ctrl+J elsewhere)."""
    return "Option+Enter" if sys.platform == "darwin" else "Ctrl+J"

