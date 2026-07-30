"""Draft acceptance criteria for a DevOps goal from objectives."""

from __future__ import annotations

from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from dcoder.model.factory import create_model

GOAL_RUBRIC_SYSTEM_PROMPT = (
    "You draft minimal acceptance criteria for a coding agent goal.\n\n"
    "Return only a flat Markdown bullet list of criteria (usually 2-5 bullets) "
    "with no heading, nesting, preamble, or closing prose. For a new proposal or "
    "rejection-based regeneration, preserve the objective.\n\n"
    "Each bullet must be short, concrete, outcome-focused, and necessary to determine "
    "whether the goal is complete. Remove overlap and combine redundant checks. Preserve "
    "explicit user constraints, names, paths, commands, and required wording verbatim where practical.\n\n"
    "Do not invent requirements or implementation details. Describe observable results "
    "rather than how to implement them. Do not start implementing the goal."
)

DEVOPS_RUBRIC_SYSTEM_PROMPT = GOAL_RUBRIC_SYSTEM_PROMPT

def _goal_rubric_human_prompt(
    objective: str,
    *,
    feedback: str | None = None,
    previous_criteria: str | None = None,
) -> str:
    parts = [
        "<goal>",
        objective,
        "</goal>",
    ]
    if feedback:
        parts.extend([
            "",
            "The user rejected the previous criteria. Regenerate the criteria entirely using this feedback; do not merely patch the prior list."
        ])
        if previous_criteria:
            parts.extend([
                "",
                "<previous_criteria>",
                previous_criteria,
                "</previous_criteria>",
            ])
        parts.extend([
            "",
            "<user_feedback>",
            feedback,
            "</user_feedback>",
        ])
    return "\n".join(parts)

def generate_rubric(
    objective: str,
    *,
    model_spec: str | None = None,
    feedback: str | None = None,
    previous_criteria: str | None = None,
) -> str:
    """Invoke LLM with DEVOPS_RUBRIC_SYSTEM_PROMPT to output bullet-point criteria."""
    model_res = create_model(model_spec)
    response = model_res.model.invoke(
        [
            SystemMessage(content=DEVOPS_RUBRIC_SYSTEM_PROMPT),
            HumanMessage(
                content=_goal_rubric_human_prompt(
                    objective,
                    feedback=feedback,
                    previous_criteria=previous_criteria,
                )
            ),
        ]
    )
    # Extract content from response
    content = getattr(response, "content", "")
    if not isinstance(content, str):
        content = str(content)
    return content.strip()
