"""Template-based prompt resolution with pluggable slots."""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from dcoder.config.settings import settings

logger = logging.getLogger("dcoder")

@dataclass
class PromptContext:
    mode: str = "interactive"
    model_name: str = ""
    model_provider: str = ""
    sandbox_provider: str | None = None
    working_dir: str = ""
    skill_paths: list[str] = field(default_factory=list)
    context_limit: int | None = None
    unsupported_modalities: list[str] = field(default_factory=list)


@dataclass
class PromptSlot:
    name: str
    resolver: Callable[[PromptContext], str]


class PromptResolver:
    """Template-based prompt resolution with pluggable slots."""

    def __init__(self, template_path: Path):
        self._template_path = template_path
        self._slots: dict[str, PromptSlot] = {}

    def register_slot(self, slot: PromptSlot) -> None:
        self._slots[slot.name] = slot

    def resolve(self, ctx: PromptContext) -> str:
        if not self._template_path.exists():
            logger.warning("Prompt template path not found: %s", self._template_path)
            return ""

        result = self._template_path.read_text(encoding="utf-8")
        for name, slot in self._slots.items():
            placeholder = f"{{{name}}}"
            if placeholder in result:
                result = result.replace(placeholder, slot.resolver(ctx))

        # Check for unreplaced placeholders
        unreplaced = re.findall(r"\{[a-z_]+\}", result)
        if unreplaced:
            logger.warning("Unreplaced placeholders in prompt: %s", unreplaced)

        return result


# ── Slot Resolvers ───────────────────────────────────────

def resolve_mode(ctx: PromptContext) -> str:
    if ctx.mode == "interactive":
        return "an interactive TUI session on the user's computer"
    return "non-interactive (headless) mode"


def resolve_preamble(ctx: PromptContext) -> str:
    if ctx.mode == "interactive":
        return (
            "You are running in interactive mode. If you are unsure about the user's requirements, "
            "you should ask clarifying questions instead of making assumptions."
        )
    return (
        "You are running in non-interactive (headless) mode. Proceed with the task autonomously. "
        "Do NOT ask questions."
    )


def resolve_ambiguity(ctx: PromptContext) -> str:
    if ctx.mode == "interactive":
        return "- If the request is ambiguous or underspecified, ask for clarification. Don't assume design details."
    return "- If the request is ambiguous, make reasonable assumptions consistent with the codebase and proceed."


def resolve_model_identity(ctx: PromptContext) -> str:
    section = "### Model Identity\n\n"
    if ctx.model_name:
        section += f"You are running as model `{ctx.model_name}`"
        if ctx.model_provider:
            section += f" (provider: {ctx.model_provider})"
        section += ".\n"
    if ctx.context_limit:
        section += f"Your context window is {ctx.context_limit:,} tokens.\n"
    if ctx.unsupported_modalities:
        mods = ", ".join(ctx.unsupported_modalities)
        section += f"{mods} input is not available for this model.\n"
    section += "\n"
    return section


def resolve_working_dir(ctx: PromptContext) -> str:
    return f"### Working Directory\n\nYour current working directory is `{ctx.working_dir}`.\n\n"


def resolve_skills_path(ctx: PromptContext) -> str:
    if ctx.skill_paths:
        return ctx.skill_paths[0]
    return ""


def resolve_todo_guidance(ctx: PromptContext) -> str:
    if ctx.mode == "interactive":
        return (
            "Use the todo list tool to plan and track your steps for any task that has 2 or more steps. "
            "Mark them in progress and completed as you go to give the user visibility."
        )
    return "Manage your task progression silently."


def resolve_devops_context(ctx: PromptContext) -> str:
    devops_path = Path(__file__).parent / "templates" / "devops_system_prompt.md"
    if devops_path.is_file():
        return devops_path.read_text(encoding="utf-8")
    return ""


def resolve_tool_guidance(ctx: PromptContext) -> str:
    return (
        "Use read_file, edit_file, or write_file instead of generic shell commands whenever possible. "
        "Run validation tests before declaring a task completed."
    )


def create_default_resolver(template_path: Path | None = None) -> PromptResolver:
    """Create a PromptResolver with all default DCoder slots registered."""
    target_path = template_path or Path(__file__).parent / "templates" / "system_prompt.md"
    resolver = PromptResolver(target_path)

    resolver.register_slot(PromptSlot("mode_description", resolve_mode))
    resolver.register_slot(PromptSlot("interactive_preamble", resolve_preamble))
    resolver.register_slot(PromptSlot("ambiguity_guidance", resolve_ambiguity))
    resolver.register_slot(PromptSlot("model_identity_section", resolve_model_identity))
    resolver.register_slot(PromptSlot("working_dir_section", resolve_working_dir))
    resolver.register_slot(PromptSlot("skills_path", resolve_skills_path))
    resolver.register_slot(PromptSlot("todo_guidance", resolve_todo_guidance))
    resolver.register_slot(PromptSlot("devops_context", resolve_devops_context))
    resolver.register_slot(PromptSlot("tool_guidance", resolve_tool_guidance))

    return resolver


def get_system_prompt(
    *,
    assistant_id: str = "dcoder",
    sandbox_type: str | None = None,
    interactive: bool = True,
    cwd: str | Path | None = None,
) -> str:
    """Resolve and return the fully populated system prompt."""
    resolver = create_default_resolver()
    
    effective_cwd = Path(cwd or Path.cwd()).resolve()
    skill_dir = settings.get_user_skills_dir(assistant_id)
    
    ctx = PromptContext(
        mode="interactive" if interactive else "headless",
        model_name=settings.model_name or "",
        model_provider=settings.model_provider or "",
        sandbox_provider=sandbox_type,
        working_dir=str(effective_cwd),
        skill_paths=[str(skill_dir)],
        context_limit=settings.model_context_limit,
        unsupported_modalities=list(settings.model_unsupported_modalities),
    )
    
    return resolver.resolve(ctx)
