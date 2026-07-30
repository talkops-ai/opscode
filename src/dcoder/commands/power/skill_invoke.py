"""``/skill:<name>`` — Dynamic skill invocation by name.

Reference: deepagents_code/app.py L12284, L12593.
Dispatched from the router via prefix matching on ``/skill:``.
"""

from __future__ import annotations

import logging

from dcoder.commands._base import BaseCommandHandler, CommandContext, CommandResult
from dcoder.commands._types import BypassTier, CommandCategory, SafetyLevel

logger = logging.getLogger(__name__)


class SkillInvokeHandler(BaseCommandHandler):
    """Load and invoke a discovered skill by name.

    Usage:
      ``/skill:web-research find recent CVEs``
      ``/skill:remember``
      ``/skill:terraform-module create vpc``

    The router dispatches ``/skill:*`` commands here via prefix matching
    (matching dcode's ``cmd.startswith("/skill:")`` pattern).
    """

    @property
    def name(self) -> str:
        # Special prefix — handled by router startswith() check
        return "/skill:"

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.POWER

    @property
    def safety_level(self) -> SafetyLevel:
        # Untrusted skills may run code — moderate risk
        return SafetyLevel.LOW_RISK

    @property
    def bypass_tier(self) -> BypassTier:
        return BypassTier.QUEUED

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from dcoder.skills.invocation import (
            build_skill_invocation_envelope,
            parse_skill_command,
        )

        skill_name, args = parse_skill_command(ctx.raw_command)
        if not skill_name:
            return CommandResult(
                success=False,
                message="Usage: /skill:<name> [args]\n\n"
                "Use `/skills` to see available skills.",
            )

        # Resolve skill from registry
        skill = self._resolve_skill(ctx, skill_name)
        if skill is None:
            return CommandResult(
                success=False,
                message=f"Skill `{skill_name}` not found.\n\n"
                "Use `/skills` to see available skills.",
            )

        # Load SKILL.md content
        content = self._load_skill_content(skill)
        if content is None:
            return CommandResult(
                success=False,
                message=f"Could not load SKILL.md for `{skill_name}`.",
            )

        # Trust check for untrusted skills
        if not self._check_trust(ctx, skill):
            return CommandResult(
                success=False,
                message=f"Skill `{skill_name}` is not trusted. "
                "Use `/skills` to review and trust it first.",
            )

        # Build invocation envelope
        envelope = build_skill_invocation_envelope(skill, content, args)

        # Send to agent
        app = ctx.app
        if app is not None and hasattr(app, "send_agent_message"):
            try:
                await app.send_agent_message(
                    envelope.prompt,
                    **envelope.message_kwargs,
                )
                return CommandResult(
                    success=True,
                    message=None,
                    mount_as_app_message=False,
                )
            except Exception as exc:
                logger.warning("Failed to invoke skill %s: %s", skill_name, exc)
                return CommandResult(
                    success=False,
                    message=f"Failed to invoke skill `{skill_name}`: {exc}",
                )

        return CommandResult(
            success=True,
            message=f"Skill `{skill_name}` loaded but agent is not connected.\n"
            "The skill will be invoked when the agent reconnects.",
        )

    def _resolve_skill(self, ctx: CommandContext, name: str) -> dict | None:
        """Resolve a skill by name from the app's discovered skills."""
        app = ctx.app
        if app is None:
            return None

        # Try app.get_discovered_skills()
        if hasattr(app, "get_discovered_skills"):
            skills = app.get_discovered_skills()
            for skill in skills:
                skill_name = skill.get("name", "").lower()
                if skill_name == name:
                    return skill
                # Also match without plugin prefix (e.g., "plugin:sub:skill" → "skill")
                if ":" in skill_name and skill_name.rsplit(":", 1)[-1] == name:
                    return skill

        return None

    def _load_skill_content(self, skill: dict) -> str | None:
        """Read the SKILL.md file for a skill."""
        from pathlib import Path

        skill_path = skill.get("path", "")
        if not skill_path:
            return None

        skill_md = Path(skill_path)
        if not skill_md.is_file():
            # Try SKILL.md in the directory
            skill_md = Path(skill_path) / "SKILL.md"

        if not skill_md.is_file():
            return None

        try:
            from dcoder.skills.loader import load_skill_content

            return load_skill_content(str(skill_md))
        except Exception:
            try:
                return skill_md.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return None

    def _check_trust(self, ctx: CommandContext, skill: dict) -> bool:
        """Check if a skill is trusted (built-in and user skills are always trusted)."""
        source = skill.get("source", "")
        # Built-in and user skills are always trusted
        if source in {"built-in", "user"}:
            return True

        # Check trust store for project/plugin skills
        try:
            from dcoder.skills.trust import SkillTrustStore

            store = SkillTrustStore()
            from pathlib import Path

            return store.is_trusted(skill.get("name", ""), Path(skill.get("path", "")))
        except Exception:
            return True  # Default to trusted if trust store unavailable
