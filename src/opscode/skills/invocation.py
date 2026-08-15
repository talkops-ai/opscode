"""Skill invocation helpers — build prompts and metadata for /skill:<name>."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class SkillInvocationEnvelope:
    """Structured prompt and checkpoint metadata for a skill invocation.

    Attributes:
        prompt: Composed prompt that wraps SKILL.md content with
            invocation instructions.
        message_kwargs: Extra fields merged into the initial HumanMessage.
    """

    prompt: str
    message_kwargs: dict[str, Any]


def build_skill_invocation_envelope(
    skill: dict[str, Any],
    content: str,
    args: str = "",
) -> SkillInvocationEnvelope:
    """Build the wrapped prompt and persisted metadata for a skill.

    Args:
        skill: Loaded skill metadata dict.
        content: Raw SKILL.md content.
        args: Optional user request appended after the skill body.

    Returns:
        A ``SkillInvocationEnvelope`` with the composed prompt and
        ``message_kwargs`` containing persisted skill metadata.
    """
    prompt = (
        f"I'm invoking the skill `{skill['name']}`. "
        "Below are the full instructions from the skill's SKILL.md file. "
        "Follow these instructions to complete the task.\n\n"
        f"---\n{content}\n---"
    )
    if args:
        prompt += f"\n\n**User request:** {args}"

    message_kwargs = {
        "additional_kwargs": {
            "__skill": {
                "name": skill["name"],
                "description": str(skill.get("description", "")),
                "source": str(skill.get("source", "")),
                "args": args,
            },
        },
    }
    return SkillInvocationEnvelope(prompt=prompt, message_kwargs=message_kwargs)


def parse_skill_command(command: str) -> tuple[str, str]:
    """Extract skill name and args from a ``/skill:<name>`` command.

    Args:
        command: The full command string (e.g., ``/skill:web-research find X``).

    Returns:
        Tuple of ``(skill_name, args)``.
        The skill name is normalized to lowercase.  Both are empty strings
        when the command has no skill name after the prefix.
    """
    after_prefix = command[len("/skill:"):].strip()
    parts = after_prefix.split(maxsplit=1)
    if not parts or not parts[0]:
        return "", ""
    skill_name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    return skill_name, args


# Built-in skill names that have a dedicated top-level slash command.
STATIC_SKILL_ALIASES: frozenset[str] = frozenset({"remember", "skill-creator"})
