"""Unified slash-command registry for DCoder.

Every slash command is declared once as a `SlashCommand` entry in `COMMANDS`.
Bypass-tier frozensets and autocomplete entries are derived automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, NamedTuple



class BypassTier(StrEnum):
    """Classification that controls whether a command can skip the message queue."""

    ALWAYS = "always"
    """Execute regardless of any busy state."""

    CONNECTING = "connecting"
    """Bypass only during initial server connection."""

    IMMEDIATE_UI = "immediate_ui"
    """Open modal UI immediately; real work deferred via callback."""

    IMMEDIATE = "immediate"
    """Execute immediately without queuing; does not open modal UI."""

    SIDE_EFFECT_FREE = "side_effect_free"
    """Execute side effect immediately; defer chat output until idle."""

    QUEUED = "queued"
    """Must wait in the queue when the app is busy."""


class CommandEntry(NamedTuple):
    """Projection carrying only fields needed for autocomplete."""

    name: str
    description: str
    hidden_keywords: str = ""
    argument_hint: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class SlashCommand:
    """A single slash-command definition."""

    name: str
    description: str
    bypass_tier: BypassTier
    hidden_keywords: str = ""
    argument_hint: str = ""
    aliases: tuple[str, ...] = ()

    def to_entry(self) -> CommandEntry:
        """Project this command into a CommandEntry for autocomplete."""
        return CommandEntry(
            name=self.name,
            description=self.description,
            hidden_keywords=self.hidden_keywords,
            argument_hint=self.argument_hint,
        )


COMMANDS: tuple[SlashCommand, ...] = (
    SlashCommand(
        name="/agents",
        description="Browse and switch between available agents & subagents",
        bypass_tier=BypassTier.IMMEDIATE_UI,
        hidden_keywords="switch profile persona subagents",
    ),
    SlashCommand(
        name="/auto",
        description="Switch to Auto approval mode",
        bypass_tier=BypassTier.SIDE_EFFECT_FREE,
        hidden_keywords="approval mode classifier automatic auto-approve shift+tab",
    ),
    SlashCommand(
        name="/manual",
        description="Switch to Manual approval mode",
        bypass_tier=BypassTier.SIDE_EFFECT_FREE,
        hidden_keywords="approval mode approve prompt review shift+tab",
    ),
    SlashCommand(
        name="/yolo",
        description="Switch to YOLO approval mode (no review)",
        bypass_tier=BypassTier.SIDE_EFFECT_FREE,
        hidden_keywords="approval mode unrestricted auto-approve dangerous shift+tab",
    ),
    SlashCommand(
        name="/bug",
        description="Report a bug or provide feedback",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="bug feedback report issue problem error crash",
        aliases=("/feedback",),
    ),
    SlashCommand(
        name="/clear",
        description="Clear the chat and start a new thread",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="reset new clean",
    ),
    SlashCommand(
        name="/compact",
        description="Summarize and offload older conversation history to free context window space",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="compact offload summarize context free",
        aliases=("/offload",),
    ),
    SlashCommand(
        name="/context",
        description="Display unified context window token usage and loaded resource counts",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="context window tokens usage capacity resources attached",
    ),
    SlashCommand(
        name="/copy",
        description="Copy the latest assistant message to clipboard",
        bypass_tier=BypassTier.SIDE_EFFECT_FREE,
        hidden_keywords="clipboard copy",
    ),
    SlashCommand(
        name="/cost",
        description="Display current session token usage and estimates",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="cost tokens usage metrics billing price",
        aliases=("/tokens",),
    ),
    SlashCommand(
        name="/effort",
        description="Set reasoning effort level for current model",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="reasoning thinking level budget effort depth",
        argument_hint="[low|medium|high|max|clear]",
    ),
    SlashCommand(
        name="/exit",
        description="Exit the application",
        bypass_tier=BypassTier.ALWAYS,
        hidden_keywords="exit quit stop bye q",
        aliases=("/quit", "/q"),
    ),
    SlashCommand(
        name="/fast",
        description="Toggle fast mode (cheapest model with low reasoning effort)",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="fast quick speed cheap haiku flash lite",
    ),
    SlashCommand(
        name="/force-clear",
        description="Stop active work, clear the chat, and start a new thread",
        bypass_tier=BypassTier.ALWAYS,
        hidden_keywords="reset interrupt stop kill",
    ),
    SlashCommand(
        name="/goal",
        description="Set a persistent objective with acceptance criteria",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="objective criteria rubric target",
        argument_hint="[<objective>|amend <feedback>|pause|resume|show|clear|model|max-iterations]",
    ),
    SlashCommand(
        name="/help",
        description="Show help and available commands",
        bypass_tier=BypassTier.SIDE_EFFECT_FREE,
        hidden_keywords="info doc commands usage",
    ),
    SlashCommand(
        name="/mcp",
        description="Manage MCP servers and connections",
        bypass_tier=BypassTier.SIDE_EFFECT_FREE,
        hidden_keywords="servers mcp tools reconnect",
        argument_hint="[login <server> | reconnect [--force] | status]",
    ),
    SlashCommand(
        name="/model",
        description="Switch models or inspect model settings",
        bypass_tier=BypassTier.IMMEDIATE_UI,
        hidden_keywords="llm model provider switch",
        argument_hint="[provider:model] [--default [--clear]]",
    ),
    SlashCommand(
        name="/notifications",
        description="Configure notifications and warnings",
        bypass_tier=BypassTier.IMMEDIATE_UI,
        hidden_keywords="alerts warnings toasts",
    ),
    SlashCommand(
        name="/resume",
        description="Browse past thread history or resume a specific session",
        bypass_tier=BypassTier.IMMEDIATE_UI,
        hidden_keywords="continue history sessions resume back previous threads browse",
        argument_hint="[-r [ID]]",
        aliases=("/threads",),
    ),
    SlashCommand(
        name="/scrollbar",
        description="Toggle message list scrollbar visibility",
        bypass_tier=BypassTier.SIDE_EFFECT_FREE,
        hidden_keywords="scroll scrollbar toggle",
    ),
    SlashCommand(
        name="/theme",
        description="Change color theme (dark/light/custom)",
        bypass_tier=BypassTier.IMMEDIATE_UI,
        hidden_keywords="color theme dark light palette",
    ),
    SlashCommand(
        name="/timestamps",
        description="Toggle message timestamps",
        bypass_tier=BypassTier.SIDE_EFFECT_FREE,
        hidden_keywords="time timestamps clock",
    ),
    SlashCommand(
        name="/trace",
        description="Open this thread in LangSmith",
        bypass_tier=BypassTier.SIDE_EFFECT_FREE,
        hidden_keywords="langsmith trace telemetry runs smith",
    ),
    SlashCommand(
        name="/version",
        description="Show DCoder version and environment info",
        bypass_tier=BypassTier.ALWAYS,
        hidden_keywords="ver build info",
    ),
    SlashCommand(
        name="/config",
        description="View and manage DCoder configuration",
        bypass_tier=BypassTier.IMMEDIATE_UI,
        hidden_keywords="config settings preferences environment env vars",
        argument_hint="[show|set <key> <value>|reset <key>|path]",
    ),
    SlashCommand(
        name="/doctor",
        description="Run diagnostic health checks on DCoder environment",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="doctor diagnose health check debug troubleshoot deps dependencies",
    ),
    SlashCommand(
        name="/login",
        description="Open auth manager to manage API keys and credentials",
        bypass_tier=BypassTier.IMMEDIATE_UI,
        hidden_keywords="auth login connect api key credentials provider",
        aliases=("/auth", "/connect"),
    ),
    SlashCommand(
        name="/logout",
        description="Revoke stored API credentials for current session",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="auth logout disconnect revoke credentials",
    ),
    SlashCommand(
        name="/permissions",
        description="View and manage agent permission scopes",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="permissions access control allowed denied trust safety sandbox",
        argument_hint="[show|grant <scope>|revoke <scope>|reset]",
    ),
    SlashCommand(
        name="/plugins",
        description="Browse and manage installed plugins",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="plugins extensions marketplace addons install manage",
    ),
    SlashCommand(
        name="/skills",
        description="List all available tools, MCP tools, and skills",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="skills tools capabilities list available installed functions",
        aliases=("/tools",),
    ),
    # ── Power User Commands (Phase 4) ──────────────────
    SlashCommand(
        name="/rubric",
        description="Set acceptance criteria for quality gating",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="rubric criteria quality gate grading acceptance",
        argument_hint="[set <criteria>|next <criteria>|show|clear|file <path>|model|max-iterations]",
        aliases=("/criteria",),
    ),
    SlashCommand(
        name="/memory",
        description="Manage persisted conversation learnings and preferences",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="memory remember preferences learnings store save",
        argument_hint="[show|save <key> <content>|get <key>|delete <key>|clear]",
    ),
    SlashCommand(
        name="/remember",
        description="Extract learnings from conversation or save a memory directly",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="remember learn save preference",
        argument_hint="[<text>]",
    ),
    SlashCommand(
        name="/review",
        description="Run code review on uncommitted changes",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="review code diff git changes",
        aliases=("/code-review",),
    ),
    SlashCommand(
        name="/reload",
        description="Hot-reload configuration, skills, themes, and environment",
        bypass_tier=BypassTier.QUEUED,
        hidden_keywords="reload refresh config skills themes env",
    ),
    SlashCommand(
        name="/restart",
        description="Immediately restart the background agent server process",
        bypass_tier=BypassTier.ALWAYS,
        hidden_keywords="restart reset server reconnect kill",
    ),
    SlashCommand(
        name="/install",
        description="Install an optional extra package or provider dependency",
        bypass_tier=BypassTier.QUEUED,
        argument_hint="<extra|package> [--package] [--force]",
        hidden_keywords="install pip uv package add",
    ),
    SlashCommand(
        name="/update",
        description="Check for and install DCoder software updates",
        bypass_tier=BypassTier.QUEUED,
        argument_hint="[--deps] [--prerelease]",
        hidden_keywords="update upgrade version check latest",
    ),
    SlashCommand(
        name="/auto-update",
        description="Toggle automatic update checks on startup",
        bypass_tier=BypassTier.SIDE_EFFECT_FREE,
        argument_hint="[on|off|status]",
        hidden_keywords="auto-update autoupdate check startup",
    ),
)


def _build_bypass_set(tier: BypassTier) -> frozenset[str]:
    """Build a lookup frozenset of command names for a specific bypass tier."""
    names: set[str] = set()
    for cmd in COMMANDS:
        if cmd.bypass_tier == tier:
            names.add(cmd.name)
            for alias in cmd.aliases:
                names.add(alias)
    return frozenset(names)


ALWAYS_IMMEDIATE: frozenset[str] = _build_bypass_set(BypassTier.ALWAYS)
IMMEDIATE_UI_CMDS: frozenset[str] = _build_bypass_set(BypassTier.IMMEDIATE_UI)


def get_command(name_or_alias: str) -> SlashCommand | None:
    """Find a SlashCommand by canonical name or alias."""
    target = name_or_alias.lower().strip()
    for cmd in COMMANDS:
        if cmd.name == target or target in cmd.aliases:
            return cmd
    return None


_STATIC_SKILL_ALIASES: frozenset[str] = frozenset({"remember"})
"""Built-in skill names that have a dedicated top-level slash command."""


def build_skill_commands(skills: list[Any]) -> list[SlashCommand]:
    """Dynamically generate SlashCommands from discovered skills.

    Skills that already have a dedicated slash command in `COMMANDS`
    (e.g., `remember` → `/remember`) are excluded to avoid duplicate
    autocomplete entries.
    """
    skill_cmds: list[SlashCommand] = []
    for skill in skills:
        if isinstance(skill, dict):
            name = skill.get("name", "")
            desc = skill.get("description", "")
        else:
            name = getattr(skill, "name", "")
            desc = getattr(skill, "description", "")

        if name and name.lower() not in _STATIC_SKILL_ALIASES:
            cmd_name = f"/{name.lower().replace('_', '-')}"
            skill_cmds.append(
                SlashCommand(
                    name=cmd_name,
                    description=f"Skill: {desc or name}",
                    bypass_tier=BypassTier.QUEUED,
                    hidden_keywords=f"skill {name}",
                )
            )
    return skill_cmds


def get_all_entries(extra_commands: list[SlashCommand] | None = None) -> list[CommandEntry]:
    """Return CommandEntry list for all registered commands and optional skills, including aliases."""
    entries: list[CommandEntry] = []
    all_cmds = list(COMMANDS)
    if extra_commands:
        all_cmds.extend(extra_commands)

    for cmd in all_cmds:
        entries.append(cmd.to_entry())
        for alias in cmd.aliases:
            entries.append(
                CommandEntry(
                    name=alias,
                    description=f"Alias for {cmd.name} — {cmd.description}",
                    hidden_keywords=cmd.hidden_keywords,
                    argument_hint=cmd.argument_hint,
                )
            )
    return entries


def get_slash_commands() -> tuple[SlashCommand, ...]:
    """Return all defined SlashCommand instances."""
    return COMMANDS

