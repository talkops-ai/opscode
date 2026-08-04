"""DCoder prompts modules."""

import logging
import re
from pathlib import Path
from typing import Sequence

logger = logging.getLogger("dcoder")

# Regex to find the ### Model Identity block for ConfigurableModelMiddleware to patch
MODEL_IDENTITY_RE = re.compile(
    r"^### Model Identity.*?(?=\n### |\Z)", re.MULTILINE | re.DOTALL
)

def build_model_identity_section(
    name: str | None,
    provider: str | None = None,
    context_limit: int | None = None,
    unsupported_modalities: frozenset[str] = frozenset(),
) -> str:
    """Build the `### Model Identity` section for the system prompt.

    Args:
        name: Model identifier (e.g. `claude-opus-4-6`).
        provider: Provider identifier (e.g. `anthropic`).
        context_limit: Max input tokens from the model profile.
        unsupported_modalities: Input modalities not indicated as supported by
            the model profile (e.g. `{"audio", "video"}`).

    Returns:
        The section text including the heading and trailing newline,
        or an empty string if `name` is falsy.
    """
    if not name:
        return ""
    section = f"### Model Identity\n\nYou are running as model `{name}`"
    if provider:
        section += f" (provider: {provider})"
    section += ".\n"
    if context_limit:
        section += f"Your context window is {context_limit:,} tokens.\n"
    if unsupported_modalities:
        items = sorted(unsupported_modalities)
        if len(items) == 1:
            joined = items[0]
        elif len(items) == 2:
            joined = f"{items[0]} and {items[1]}"
        else:
            joined = ", ".join(items[:-1]) + f", and {items[-1]}"
        section += (
            f"{joined.capitalize()} input may not be available for this model. "
            "Do not attempt to read or process these content types.\n"
        )
    section += "\n"
    return section


def get_base_system_prompt(
    assistant_id: str = "dcoder",
    interactive: bool = True,
    cwd: str | Path | None = None,
    fs_tools: list[str] | None = None,
    model_name: str | None = None,
    model_provider: str | None = None,
    model_context_limit: int | None = None,
) -> str:
    """Get the DCoder base system prompt and resolve placeholders dynamically."""
    prompt_dir = Path(__file__).parent / "templates"
    template_path = prompt_dir / "system_prompt.md"
    
    if not template_path.exists():
        return ""
        
    template = template_path.read_text(encoding="utf-8")

    # 1. Mode and Interaction Guidance
    if interactive:
        mode_description = "an interactive TUI session on the user's computer"
        interactive_preamble = (
            "The user sends you messages and you respond with text and tool "
            "calls. Your tools run on the user's machine. The user can see "
            "your responses and tool outputs in real time, so keep them "
            "informed — but don't over-explain."
        )
        ambiguity_guidance = (
            "- If the request is ambiguous, ask questions before acting.\n"
            "- If asked how to approach something, explain first, then act."
        )
        todo_guidance = (
            "6. When first creating a todo list for a task, ALWAYS ask the user if "
            "the plan looks good before starting work\n"
            '   - Create the todos, then ask: "Does this plan '
            'look good?" or similar\n'
            "   - Wait for the user's response before marking the first todo as "
            "in_progress\n"
            "7. Update todo status promptly as you complete each item"
        )
    else:
        mode_description = "non-interactive (headless) mode"
        interactive_preamble = (
            "You received a single task and must complete it fully and "
            "autonomously. There is no human available to answer follow-up "
            "questions, so do NOT ask for clarification — make reasonable "
            "assumptions and proceed."
        )
        ambiguity_guidance = (
            "- Do NOT ask clarifying questions — there is no human to answer "
            "them. Make reasonable assumptions and proceed.\n"
            "- If you encounter ambiguity, choose the most reasonable "
            "interpretation and note your assumption briefly.\n"
            "- Always use non-interactive command variants — no human is "
            "available to respond to prompts. Examples: `npm init -y` not "
            "`npm init`, `apt-get install -y` not `apt-get install`, "
            "`yes |` or `--no-input`/`--non-interactive` flags where "
            "available. Never run commands that block waiting for stdin."
        )
        todo_guidance = (
            "6. There is no human operator in this mode — do NOT ask the user to "
            "approve your plan or wait for a reply.\n"
            "   After you create todos for a multi-step task, mark the first item "
            "`in_progress` immediately and start work.\n"
            "   If the plan needs adjustment, revise the todo list yourself; do "
            "not block on human confirmation.\n"
            "7. Update todo status promptly as you complete each item"
        )

    # 2. Filesystem Tool Guidance
    if fs_tools and len(fs_tools) < 5:
        available = ", ".join(f"`{t}`" for t in sorted(fs_tools))
        filesystem_tool_guidance = (
            f"You have restricted access to the filesystem. Only the following "
            f"file tools are available: {available}.\n"
        )
    else:
        filesystem_tool_guidance = ""

    # 3. Model Identity
    model_identity_section = build_model_identity_section(
        model_name,
        provider=model_provider,
        context_limit=model_context_limit,
    )

    # 4. Working Directory
    if cwd is None:
        try:
            resolved_cwd = Path.cwd()
        except OSError:
            logger.warning("Could not determine working directory for system prompt")
            resolved_cwd = Path()
    else:
        resolved_cwd = Path(cwd)

    working_dir_section = (
        f"### Current Working Directory\n\n"
        f"The filesystem backend is currently operating in: `{resolved_cwd}`\n\n"
        f"### File System and Paths\n\n"
        f"**IMPORTANT - Path Handling:**\n"
        f"- All file paths must be absolute paths (e.g., `{resolved_cwd}/file.txt`)\n"
        f"- Use the working directory to construct absolute paths\n"
        f"- Example: To create a file in your working directory, "
        f"use `{resolved_cwd}/research_project/file.md`\n"
        f"- Never use relative paths - always construct full absolute paths\n\n"
    )

    # 5. Skills Path
    skills_path = f"Skills are loaded from your `{assistant_id}` skills directory."

    # Perform simple string replacement for placeholders
    result = (
        template.replace("{mode_description}", mode_description)
        .replace("{interactive_preamble}", interactive_preamble)
        .replace("{ambiguity_guidance}", ambiguity_guidance)
        .replace("{todo_guidance}", todo_guidance)
        .replace("{filesystem_tool_guidance}", filesystem_tool_guidance)
        .replace("{model_identity_section}", model_identity_section)
        .replace("{working_dir_section}", working_dir_section)
        .replace("{skills_path}", skills_path)
    )

    unreplaced = re.findall(r"\{[a-z_]+\}", result)
    if unreplaced:
        logger.warning("System prompt contains unreplaced placeholders: %s", unreplaced)

    return result

__all__ = ["get_base_system_prompt", "build_model_identity_section", "MODEL_IDENTITY_RE"]
