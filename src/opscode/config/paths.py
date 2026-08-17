"""Centralized filesystem-path definitions for opscode.

This module is the **single source of truth** for every directory and file
opscode reads or writes at runtime. It is intentionally dependency-free (no
sibling-module imports, no third-party packages) so any module — including the
startup-critical ``main.py`` — can import from it without triggering a chain of
expensive imports.
"""

from __future__ import annotations

import errno
import logging
from enum import StrEnum
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────

ENV_PREFIX: Final[str] = "OPSCODE_"
"""All opscode-specific env vars use this prefix."""

DEFAULT_AGENT_NAME: Final[str] = "agent"
"""Default agent / assistant identifier when no ``-a`` flag is given."""

# ── Root directories ─────────────────────────────────────

DATA_DIR: Final[Path] = Path.home() / ".opscode"
"""``~/.opscode/`` — Top-level user data directory."""

STATE_DIR: Final[Path] = DATA_DIR / ".state"
"""``~/.opscode/.state/`` — Machine-managed state (never hand-edit)."""

AGENTS_SHARED_DIR: Final[Path] = Path.home() / ".agents"
"""``~/.agents/`` — Tool-agnostic data (shared across AI CLIs)."""

# ── User-facing config files (human-editable) ────────────

CONFIG_PATH: Final[Path] = DATA_DIR / "config.toml"
"""``~/.opscode/config.toml`` — Main configuration file."""

GLOBAL_ENV_PATH: Final[Path] = DATA_DIR / ".env"
"""``~/.opscode/.env`` — Global env vars / API keys."""

HOOKS_PATH: Final[Path] = DATA_DIR / "hooks.json"
"""``~/.opscode/hooks.json`` — Lifecycle hooks."""

GLOBAL_MCP_PATH: Final[Path] = DATA_DIR / ".mcp.json"
"""``~/.opscode/.mcp.json`` — Global MCP server definitions."""

CONVERSATION_HISTORY_DIR: Final[Path] = DATA_DIR / "conversation_history"
"""``~/.opscode/conversation_history/`` — Offload conversation logs."""

# ── Managed state files (.state/) ────────────────────────

AUTH_PATH: Final[Path] = STATE_DIR / "auth.json"
"""``~/.opscode/.state/auth.json`` — Credential store (OpenRouter/gateway).
Individual provider keys (OpenAI, Gemini, Anthropic, LangSmith) go to ``.env``.
"""

SESSIONS_DB_PATH: Final[Path] = STATE_DIR / "sessions.db"
"""``~/.opscode/.state/sessions.db`` — SQLite conversation checkpoints."""

HISTORY_PATH: Final[Path] = STATE_DIR / "history.jsonl"
"""``~/.opscode/.state/history.jsonl`` — Command input history."""

RECENT_MODELS_PATH: Final[Path] = STATE_DIR / "recent_models.json"
"""``~/.opscode/.state/recent_models.json`` — Last ``/model`` switch."""

MCP_TRUST_PATH: Final[Path] = STATE_DIR / "mcp_trust.json"
"""``~/.opscode/.state/mcp_trust.json`` — Saved MCP project approvals."""

SKILL_TRUST_PATH: Final[Path] = STATE_DIR / "skill_trust.json"
"""``~/.opscode/.state/skill_trust.json`` — Skill trust decisions."""

ONBOARDING_MARKER: Final[Path] = STATE_DIR / "onboarding_complete"
"""``~/.opscode/.state/onboarding_complete`` — First-run marker."""

# ── Plugin directory and state files ─────────────────────────

PLUGINS_DIR: Final[Path] = DATA_DIR / "plugins"
"""``~/.opscode/plugins/`` — Top-level plugin storage root (cache, data, marketplaces)."""

PLUGIN_CACHE_DIR: Final[Path] = PLUGINS_DIR / "cache"
"""``~/.opscode/plugins/cache/`` — Downloaded versioned plugin archives."""

PLUGIN_DATA_DIR: Final[Path] = PLUGINS_DIR / "data"
"""``~/.opscode/plugins/data/`` — Per-plugin persistent data."""

PLUGIN_MARKETPLACES_DIR: Final[Path] = PLUGINS_DIR / "marketplaces"
"""``~/.opscode/plugins/marketplaces/`` — Cloned marketplace repository caches."""

PLUGIN_INSTALLED_PATH: Final[Path] = STATE_DIR / "installed_plugins.json"
"""``~/.opscode/.state/installed_plugins.json`` — Installed plugin registry."""

PLUGIN_STATE_PATH: Final[Path] = STATE_DIR / "plugin_state.json"
"""``~/.opscode/.state/plugin_state.json`` — Plugin runtime state."""

PLUGIN_MARKETPLACES_PATH: Final[Path] = STATE_DIR / "plugin_marketplaces.json"
"""``~/.opscode/.state/plugin_marketplaces.json`` — Marketplace source registry."""

# ── Scoped settings files (Claude Code pattern) ─────────

USER_SETTINGS_PATH: Final[Path] = DATA_DIR / "settings.json"
"""``~/.opscode/settings.json`` — User-scope settings (enabledPlugins, etc.).

Matches Claude Code's ``~/.claude/settings.json`` layout.
"""


def project_settings_path(project_root: Path) -> Path:
    """Return ``{project_root}/.opscode/settings.json`` — project-scope settings.

    This file is committed to git and shared with all collaborators.
    Schema: ``{ "enabledPlugins": { "plugin@marketplace": true } }``
    """
    return project_opscode_dir(project_root) / "settings.json"


def project_local_settings_path(project_root: Path) -> Path:
    """Return ``{project_root}/.opscode/settings.local.json`` — local-scope settings.

    This file is gitignored (personal project overrides).
    Schema: ``{ "enabledPlugins": { "plugin@marketplace": true } }``
    """
    return project_opscode_dir(project_root) / "settings.local.json"



# ── Project root markers ─────────────────────────────────

PROJECT_ROOT_MARKERS: Final[tuple[str, ...]] = (
    ".opscode",
    ".git",
    "terragrunt.hcl",
    "Chart.yaml",
    "ansible.cfg",
    "pyproject.toml",
    "package.json",
    "Makefile",
)

# ── Keys denied in .env files ────────────────────────────

DOTENV_DENIED_ENV_KEYS: Final[frozenset[str]] = frozenset({
    "PATH", "HOME", "USER", "LOGNAME", "SHELL", "TERM", "DISPLAY",
    "LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES",
    "PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME",
    "NODE_PATH", "NODE_OPTIONS",
    "HISTFILE", "HISTSIZE",
    "SSH_AUTH_SOCK", "GPG_AGENT_INFO",
    "TMPDIR", "TEMP", "TMP",
})

# ── Fields reloadable via /reload ────────────────────────

RELOADABLE_FIELDS: Final[frozenset[str]] = frozenset({
    "openai_api_key", "anthropic_api_key", "google_api_key",
    "groq_api_key", "deepseek_api_key",
    "project_root", "shell_allow_list",
})

# DevOps-specific env vars to preserve in shell environment
DEVOPS_PRESERVE_ENV_VARS: Final[tuple[str, ...]] = (
    "KUBECONFIG", "KUBE_CONTEXT",
    "AWS_PROFILE", "AWS_REGION", "AWS_DEFAULT_REGION", "AWS_SHARED_CREDENTIALS_FILE",
    "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT", "CLOUDSDK_CORE_PROJECT",
    "AZURE_SUBSCRIPTION_ID", "AZURE_TENANT_ID",
    "ANSIBLE_CONFIG", "ANSIBLE_INVENTORY",
    "HELM_HOME", "HELM_REPOSITORY_CONFIG",
    "ARGOCD_SERVER", "ARGOCD_AUTH_TOKEN",
    "TF_CLI_CONFIG_FILE", "TERRAGRUNT_CONFIG",
)


# ── Agent / per-agent directory helpers ──────────────────

def agent_dir(name: str = DEFAULT_AGENT_NAME) -> Path:
    """Return ``~/.opscode/{name}/``.

    The default agent directory is ``~/.opscode/opscode/``.
    """
    return DATA_DIR / name


def user_skills_dir(name: str = DEFAULT_AGENT_NAME) -> Path:
    """Return ``~/.opscode/{name}/skills/``."""
    return agent_dir(name) / "skills"


def user_agents_dir(name: str = DEFAULT_AGENT_NAME) -> Path:
    """Return ``~/.opscode/{name}/agents/``."""
    return agent_dir(name) / "agents"


def user_agent_md(name: str = DEFAULT_AGENT_NAME) -> Path:
    """Return ``~/.opscode/{name}/AGENTS.md``."""
    return agent_dir(name) / "AGENTS.md"


# ── Project directory helpers ────────────────────────────

def project_opscode_dir(project_root: Path) -> Path:
    """Return ``{project_root}/.opscode/``."""
    return project_root / ".opscode"


def project_skills_dir(project_root: Path) -> Path:
    """Return ``{project_root}/.opscode/skills/``."""
    return project_opscode_dir(project_root) / "skills"


def project_agents_dir(project_root: Path) -> Path:
    """Return ``{project_root}/.opscode/agents/``."""
    return project_opscode_dir(project_root) / "agents"


def project_mcp_paths(project_root: Path) -> list[Path]:
    """Return candidate MCP config paths for a project, in precedence order.

    Precedence (highest → lowest):
      1. ``{project_root}/.mcp.json``
      2. ``{project_root}/mcp.json``
      3. ``{project_root}/.opscode/.mcp.json``
      4. ``{project_root}/.opscode/mcp.json``
    """
    return [
        project_root / ".mcp.json",
        project_root / "mcp.json",
        project_opscode_dir(project_root) / ".mcp.json",
        project_opscode_dir(project_root) / "mcp.json",
    ]


def project_agent_md_paths(project_root: Path) -> list[Path]:
    """Return candidate AGENTS.md paths for a project.

    Both loaded if present (combined, not overridden).
    """
    return [
        project_opscode_dir(project_root) / "AGENTS.md",
        project_root / "AGENTS.md",
    ]


# ── Ensure directories exist ────────────────────────────

def ensure_data_dir() -> Path:
    """Create ``~/.opscode/`` if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def ensure_state_dir() -> Path:
    """Create ``~/.opscode/.state/`` if it doesn't exist."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR


def ensure_agent_dir(name: str = DEFAULT_AGENT_NAME) -> Path:
    """Create ``~/.opscode/{name}/`` if it doesn't exist."""
    d = agent_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_plugins_dir() -> Path:
    """Create ``~/.opscode/plugins/`` if it doesn't exist."""
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    return PLUGINS_DIR


def ensure_conversation_history_dir() -> Path:
    """Create ``~/.opscode/conversation_history/`` if it doesn't exist."""
    CONVERSATION_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return CONVERSATION_HISTORY_DIR


def upsert_env_vars(env_dict: dict[str, str], env_path: Path | None = None) -> bool:
    """Upsert key-value pairs into a .env file.

    Updates existing key lines in-place, deduplicates duplicate key occurrences,
    and appends new keys atomically.

    Args:
        env_dict: Dictionary mapping environment variable names to new values.
        env_path: Target .env Path (defaults to GLOBAL_ENV_PATH).

    Returns:
        True if saved successfully, False otherwise.
    """
    import contextlib
    import tempfile

    target_path = env_path or GLOBAL_ENV_PATH
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        if target_path.exists():
            content = target_path.read_text(encoding="utf-8")
            lines = content.splitlines()

        new_lines: list[str] = []
        seen_keys: set[str] = set()

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue

            raw_key = stripped.removeprefix("export ").split("=", 1)[0].strip()
            if not raw_key:
                new_lines.append(line)
                continue

            if raw_key in env_dict:
                if raw_key not in seen_keys:
                    new_lines.append(f"{raw_key}={env_dict[raw_key]}")
                    seen_keys.add(raw_key)
            else:
                if raw_key not in seen_keys:
                    new_lines.append(line)
                    seen_keys.add(raw_key)

        for k, v in env_dict.items():
            if k not in seen_keys:
                new_lines.append(f"{k}={v}")
                seen_keys.add(k)

        final_content = "\n".join(new_lines).strip() + "\n" if new_lines else ""

        fd, tmp_path = tempfile.mkstemp(dir=target_path.parent, suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(final_content)
            Path(tmp_path).replace(target_path)
        except BaseException:
            with contextlib.suppress(OSError):
                Path(tmp_path).unlink()
            raise
        return True
    except Exception as exc:
        logger.exception("Failed to upsert env vars in %s: %s", target_path, exc)
        return False



# ── Path classification (for doctor/diagnostics) ────────

_MISSING_ERRNOS = {errno.ENOENT, errno.ENOTDIR}


class PathState(StrEnum):
    """Whether a probed path exists, is absent, or could not be read."""

    EXISTS = "exists"
    """The path is present on disk."""

    MISSING = "missing"
    """The path is absent (and its parents are readable)."""

    UNREADABLE = "unreadable"
    """Existence could not be determined because ``Path.stat()`` raised."""


def classify_path(path: Path) -> PathState:
    """Classify a path as existing, missing, or unreadable.

    Returns ``PathState.EXISTS`` for a present path, ``PathState.MISSING``
    for expected absent-path errors, and ``PathState.UNREADABLE`` when
    ``Path.stat()`` raises another ``OSError``.
    """
    try:
        path.stat()
    except OSError as exc:
        if exc.errno in _MISSING_ERRNOS:
            return PathState.MISSING
        logger.debug("Could not stat %s", path, exc_info=True)
        return PathState.UNREADABLE
    else:
        return PathState.EXISTS
