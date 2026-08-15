"""Canonical registry of `OPSCODE_*` environment variables.

Every env var the app reads whose name starts with `OPSCODE_` must
be defined here as a module-level constant.  A drift-detection test
(`tests/unit_tests/test_env_vars.py`) fails when a bare string literal
like `"OPSCODE_FOO"` appears in source code instead of a constant
imported from this module.

Import the short-name constants (e.g. `AUTO_UPDATE`, `DEBUG`) and pass them
to `os.environ.get()` instead of using raw string literals. If the env var is
ever renamed, only the value here changes.

!!! note

    `resolve_env_var` also supports a dynamic prefix override for API keys
    and provider credentials: setting `OPSCODE_{NAME}` takes priority
    over `{NAME}`.  For example, `OPSCODE_OPENAI_API_KEY` overrides
    `OPENAI_API_KEY`. Only call sites that use `resolve_env_var` benefit from
    this -- direct `os.environ.get` lookups (like the constants below) do not.
    Dynamic overrides are not listed here because they mirror third-party
    variable names.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Constants — import these instead of bare string literals.
# Keep alphabetically sorted by constant name.
# ---------------------------------------------------------------------------

AUTO_UPDATE = "OPSCODE_AUTO_UPDATE"
"""Toggle automatic app updates. Enabled by default; set to a falsy value
('0', 'false', 'no', 'off', or empty) to opt out."""

COLLAPSE_PASTES = "OPSCODE_COLLAPSE_PASTES"
"""Collapse large chat-input pastes into `[Pasted text #N +M lines]` placeholders.

Enabled by default; set to a falsy value (`0`, `false`, `no`, `off`, or empty)
to disable auto-collapsing so pasted text is inserted verbatim. Parsed by
`classify_env_bool` (an unrecognized value falls through to the config value
rather than forcing the default). Also settable via `[ui].collapse_pastes` in
config.toml.
"""

DEBUG = "OPSCODE_DEBUG"
"""Enable verbose debug logging and preserve the server subprocess log.

Parsed by `is_env_truthy`: accepts `1`, `true`, `yes`, `on` (case-insensitive)
as enabled, and `0`, `false`, `no`, `off`, empty string, or unset as disabled.
"""

DEBUG_FILE = "OPSCODE_DEBUG_FILE"
"""Path for the debug log file (default: `DEFAULT_DEBUG_FILE`)."""

DEFAULT_DEBUG_FILE = "/tmp/opscode_debug.log"  # noqa: S108  # opt-in debug log
"""Default path for the debug log when `DEBUG_FILE` is unset."""

LOG_LEVEL = "OPSCODE_LOG_LEVEL"
"""Override the runtime logging level (e.g. DEBUG, INFO, WARNING).
Takes precedence over the default logging level derived from `DEBUG`.
"""

DEBUG_MCP_PROJECT_TRUST = "OPSCODE_DEBUG_MCP_PROJECT_TRUST"
"""Force the project MCP approval prompt for manual UI testing.

Set to a truthy value when launching the interactive TUI to render the
project-level MCP trust prompt without relying on an untrusted config state. If
project MCP servers are discovered, the prompt shows those real servers;
otherwise it shows a sample server. The TUI exits after the prompt response so
the debug run does not continue into TUI or server startup, and it does not
persist trust decisions.

Parsed by `is_env_truthy`: accepts `1`, `true`, `yes`, `on` as enabled.
"""

DEBUG_NOTIFICATIONS = "OPSCODE_DEBUG_NOTIFICATIONS"
"""Inject sample missing-dependency notifications at launch so the notification
center UI can be exercised without waiting for real conditions.

Does not auto-open the update modal (use `OPSCODE_DEBUG_UPDATE` for that).

Any non-empty value enables the flag (including `"0"` or `"false"`).
"""

DEBUG_ONBOARDING = "OPSCODE_DEBUG_ONBOARDING"
"""Force the onboarding flow to open on every interactive startup.

Parsed by `is_env_truthy`: accepts `1`, `true`, `yes`, `on` as enabled.
"""

DEBUG_UPDATE = "OPSCODE_DEBUG_UPDATE"
"""Inject a sample update-available notification and auto-open the update modal
at launch so the update-available flow can be exercised without waiting for a
real PyPI release.

Any non-empty value enables the flag (including `"0"` or `"false"`).
"""

DISABLED_PROJECT_MCP_SERVERS = "OPSCODE_DISABLED_PROJECT_MCP_SERVERS"
"""Comma-separated project MCP server names to always reject by name.

A user-level equivalent of `[mcp].disabled_project_servers`.

Rejection wins over approval: a name listed here is dropped even when it also
appears in `ENABLED_PROJECT_MCP_SERVERS` (or `[mcp].enabled_project_servers`)
and even when the project config is otherwise trusted. Unlike the enabled list,
this env var *unions* with (rather than replaces)
`[mcp].disabled_project_servers` — denies accumulate across sources, so neither
can silently empty a deny set in the other. This is process env the user
controls, not a repo file, so it does not weaken the user-level-only
trust boundary: a committed *project* `.env` is blocked from setting it
(see `config._PROJECT_DOTENV_DENIED_ENV_KEYS`); only the user's shell,
launch env, or global `~/.opscode/.env` can.
"""

ENABLED_PROJECT_MCP_SERVERS = "OPSCODE_ENABLED_PROJECT_MCP_SERVERS"
"""Comma-separated project MCP server names to pre-approve by name.

A user-level equivalent of `[mcp].enabled_project_servers`.

Servers named here load from an otherwise-untrusted project `.mcp.json` without
prompting (they are omitted from the interactive approval prompt), while
non-listed servers stay dropped. Like `DISABLED_PROJECT_MCP_SERVERS`, this is
user-controlled process env, not a repo file, so it does not weaken
the user-level-only trust boundary (a committed *project* `.env` cannot set it;
see `config._PROJECT_DOTENV_DENIED_ENV_KEYS`). This contract is name-based:
a project command or URL change under the same server name still matches.

When set, this replaces (takes precedence over) the
`[mcp].enabled_project_servers` TOML list.
(`DISABLED_PROJECT_MCP_SERVERS` instead *unions* with its TOML list, so a deny
is never silently emptied.)
"""

EXTERNAL_EVENT_SOCKET = "OPSCODE_EXTERNAL_EVENT_SOCKET"
"""Enable the local Unix-socket external event listener.

Parsed by `is_env_truthy`; off by default. Wire format and behavior are
considered experimental until the listener is documented in the README.
"""

EXTERNAL_EVENT_SOCKET_PATH = "OPSCODE_EXTERNAL_EVENT_SOCKET_PATH"
"""Override the default Unix-socket path for the external event listener."""

EXTRA_SKILLS_DIRS = "OPSCODE_EXTRA_SKILLS_DIRS"
"""Colon-separated paths added to the skill containment allowlist."""

EXPERIMENTAL = "OPSCODE_EXPERIMENTAL"
"""Enable experimental features across OpsCode."""

HIDE_CWD = "OPSCODE_HIDE_CWD"
"""Hide local path displays in the TUI footer and the editable-install path in
the startup splash when enabled.

Does not control the splash working-directory row, which is gated solely by
`SPLASH_SHOW_CWD`.
"""

HIDE_GIT_BRANCH = "OPSCODE_HIDE_GIT_BRANCH"
"""Hide the current git branch in the TUI footer when enabled."""

HIDE_LANGSMITH_TRACING = "OPSCODE_HIDE_LANGSMITH_TRACING"
"""Hide LangSmith tracing project/thread info in the startup splash when enabled."""

HIDE_SPLASH_VERSION = "OPSCODE_HIDE_SPLASH_VERSION"
"""Hide version and local-install details in the splash screen when enabled."""

KITTY_KEYBOARD = "OPSCODE_KITTY_KEYBOARD"
"""Override kitty-keyboard detection (`1` forces on, `0` forces off)."""

LANGSMITH_PROJECT = "OPSCODE_LANGSMITH_PROJECT"
"""Override LangSmith project name for agent traces."""

LANGSMITH_REDACT = "OPSCODE_LANGSMITH_REDACT"
"""Toggle LangSmith secret redaction for agent traces (defaults to on)."""

LANGSMITH_REPLICA_PROJECTS = "OPSCODE_LANGSMITH_REPLICA_PROJECTS"
"""Comma-separated LangSmith project names to *also* write agent traces to.

When set (and tracing is active), each agent run is dual-written to the primary
opscode project *and* one extra project via LangSmith write replicas.

Only the first listed project is used: the LangGraph server mirrors a run to a
single extra project, so any additional entries are dropped (with a warning).
The value is comma-separated for forward-compatibility, not because multiple
destinations are written today.
"""

NO_TERMINAL_ESCAPE = "OPSCODE_NO_TERMINAL_ESCAPE"
"""Disable all terminal escape/control sequence output when enabled."""

NO_UPDATE_CHECK = "OPSCODE_NO_UPDATE_CHECK"
"""Disable automatic update checking when set."""

OFFLINE = "OPSCODE_OFFLINE"
"""Disable network downloads of managed binaries (e.g. ripgrep).

Parsed by `is_env_truthy`: accepts `1`, `true`, `yes`, `on` as enabled. When
truthy, `managed_tools.ensure_ripgrep` will not attempt to download a binary
and falls back to the existing missing-tool notification + slow Python regex
path."""

OLLAMA_DISCOVERY = "OPSCODE_OLLAMA_DISCOVERY"
"""Toggle Ollama model and profile discovery probes.

Defaults to enabled. Suppress the probe when the daemon is intentionally
offline or the probe latency is undesirable. The probe is lazy and never
runs on the startup hot path. When enabled, discovery may call `/api/tags`
and `/api/show`. See `_ollama_discovery_enabled` for accepted truthy/falsy
values.
"""

ONBOARDING_INTEGRATIONS_SCREEN = "OPSCODE_ONBOARDING_INTEGRATIONS_SCREEN"
"""Show the "Installed Integrations" summary screen during first-run onboarding.

Off by default: onboarding goes straight from the name prompt to the model
selector, which already surfaces (and installs) uninstalled model providers.
Set to a truthy value to bring the standalone integrations screen back into the
flow. Parsed by `is_env_truthy`: accepts `1`, `true`, `yes`, `on` as enabled.
"""

RESTARTED_AFTER_UPDATE = "OPSCODE_RESTARTED_AFTER_UPDATE"
"""Internal sentinel recording the target version immediately before the
startup auto-update re-execs the process.

Not user-facing. The re-exec'd process consumes it and, if that same version
still reports as available (a no-op upgrade that did not change the running
version), skips auto-updating to break out of an otherwise endless
upgrade/restart loop. Set and read internally across `os.execv`.
"""

RIPGREP_INSTALLER = "OPSCODE_RIPGREP_INSTALLER"
"""Select how ripgrep is provisioned: `managed` (default) or `system`.

`managed` downloads the pinned, SHA-256-verified upstream binary into
`~/.opscode/bin` (no sudo). `system` skips that download so power users can
rely on their distro package / existing toolchain instead; the install script's
`system` mode keeps the brew/apt/cargo path. A system `rg` already on `PATH` is
reused under either setting. Unrecognized values fall back to `managed`. See
`managed_tools.ripgrep_installer`."""

SERVER_ENV_PREFIX = "OPSCODE_SERVER_"
"""Environment variable prefix used to pass CLI config to the server subprocess."""

SHELL_ALLOW_LIST = "OPSCODE_SHELL_ALLOW_LIST"
"""Comma-separated shell commands to allow (or 'recommended'/'all')."""

SHOW_HEADER = "OPSCODE_SHOW_HEADER"
"""Show Textual's native header bar at the top of the TUI when enabled."""

SHOW_LANGSMITH_REPLICA_TRACING = "OPSCODE_SHOW_LANGSMITH_REPLICA_TRACING"
"""Show LangSmith replica project info in the startup splash when enabled.

Defaults to enabled; set to a falsy value (`0`, `false`, `no`, `off`, or empty)
to hide replica tracing details from the splash while leaving tracing active.
"""

SHOW_SCROLLBAR = "OPSCODE_SHOW_SCROLLBAR"
"""Show the vertical scrollbar in the chat area when enabled.

Off by default; use the `/scrollbar` slash command or `[ui].show_scrollbar` in
config.toml to toggle. Parsed by `classify_env_bool` (an unrecognized or empty
value falls through to the config value rather than forcing the default).

When set, this env var takes precedence over the persisted `[ui].show_scrollbar`
config value on launch, so a `/scrollbar` toggle will not appear to "stick"
across restarts while the env var remains set.
"""

SHOW_URL_OPEN_TOAST = "OPSCODE_SHOW_URL_OPEN_TOAST"
"""Show a confirmation toast after clicking a URL that opens in a browser.

Defaults to enabled; set to a falsy value (`0`, `false`, `no`, `off`, or empty)
to suppress the success toast while still opening URLs normally.
"""

SPLASH_SHOW_CWD = "OPSCODE_SPLASH_SHOW_CWD"
"""Show the working-directory row in the startup welcome banner when enabled.

Off by default and independent of the status bar's `HIDE_CWD`.
"""

SPLASH_SHOW_MODEL = "OPSCODE_SPLASH_SHOW_MODEL"
"""Show the active model row in the startup welcome banner when enabled.

Off by default; the model is always visible in the status bar, so the banner
row is opt-in to avoid duplicating it.
"""

SUPPRESS_ENV_OVERRIDE_WARNING = "OPSCODE_SUPPRESS_ENV_OVERRIDE_WARNING"
"""Silence the startup warning emitted when a `OPSCODE_`-prefixed
LangSmith variable overrides its canonical counterpart (e.g. both
`LANGSMITH_API_KEY` and `OPSCODE_LANGSMITH_API_KEY` are set to
different values).

The override is intentional: the prefixed value overwrites the canonical
variable inside the Deep Agents Code process (so the LangSmith SDK, which
only reads canonical names, picks it up). The value you exported in your own
shell is unaffected, since a process cannot change its parent's environment.
Off by default; set to a truthy value (`1`, `true`, `yes`, `on`) to suppress
the warning when this coexistence is expected. Parsed by `is_env_truthy`.
"""

THEME = "OPSCODE_THEME"
"""Force the CLI to launch with this theme name when set."""

USER_ID = "OPSCODE_USER_ID"
"""Attach a user identifier to LangSmith trace metadata."""

_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSY_VALUES = frozenset({"0", "false", "no", "off", ""})


def classify_env_bool(raw: str) -> bool | None:
    """Classify a raw env-var string as a truthy, falsy, or unrecognized token.

    The single source of truth for which strings count as boolean on/off
    values; `is_env_truthy` and the config resolver both build on it so they
    agree on what "recognizably boolean" means.

    Args:
        raw: The raw (unstripped) environment-variable value.

    Returns:
        `True` for `1`/`true`/`yes`/`on`, `False` for `0`/`false`/`no`/`off`/
            empty string (case-insensitive), or `None` when the value
            is neither.
    """
    lowered = raw.strip().lower()
    if lowered in _TRUTHY_VALUES:
        return True
    if lowered in _FALSY_VALUES:
        return False
    return None


def is_env_truthy(name: str, *, default: bool = False) -> bool:
    """Return whether env var *name* is set to a recognizably truthy value.

    Unlike `bool(os.environ.get(name))`, this does not treat `"0"` or
    `"false"` as enabled. Use this for on/off flags where the user would
    reasonably expect `VAR=0` to mean "disabled".

    Args:
        name: Environment variable name (typically a `OPSCODE_*`
            constant from this module).
        default: Value returned when the variable is unset OR set to a
            value that is neither recognizably truthy nor falsy.

    Returns:
        `True` for `1`/`true`/`yes`/`on` (case-insensitive), `False` for
        `0`/`false`/`no`/`off`/empty string, or `default` otherwise.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    classified = classify_env_bool(raw)
    return default if classified is None else classified
