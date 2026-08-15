"""First-run interactive onboarding wizard for opscode."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from opscode.config.settings import settings

logger = logging.getLogger(__name__)

ONBOARDING_NAME_MEMORY_START = "<!-- opscode:onboarding-name:start -->"
ONBOARDING_NAME_MEMORY_END = "<!-- opscode:onboarding-name:end -->"

def _normalize_memory_name(name: str) -> str:
    return " ".join(name.split())

def _onboarding_name_memory_block(name: str, provider: str, cloud: str, iac: str) -> str:
    return (
        f"{ONBOARDING_NAME_MEMORY_START}\n"
        f"- The user's preferred name is \"{name}\".\n"
        f"- Preferred LLM Provider: {provider}\n"
        f"- Target Cloud: {cloud}\n"
        f"- IaC Tool Preference: {iac}\n"
        f"{ONBOARDING_NAME_MEMORY_END}"
    )

def _upsert_onboarding_name_memory(existing: str, block: str) -> str:
    start = existing.find(ONBOARDING_NAME_MEMORY_START)
    end = existing.find(ONBOARDING_NAME_MEMORY_END)
    if start != -1 and end != -1 and start < end:
        end += len(ONBOARDING_NAME_MEMORY_END)
        prefix = existing[:start].rstrip()
        suffix = existing[end:].strip()
        parts = [part for part in (prefix, block, suffix) if part]
        return "\n\n".join(parts).rstrip() + "\n"

    base = existing.rstrip()
    if not base:
        return f"## User Preferences\n\n{block}\n"
    if "## User Preferences" in base:
        return f"{base}\n\n{block}\n"
    return f"{base}\n\n## User Preferences\n\n{block}\n"

def extract_onboarding_name_block(text: str) -> str | None:
    start = text.find(ONBOARDING_NAME_MEMORY_START)
    end = text.find(ONBOARDING_NAME_MEMORY_END)
    if start == -1 or end == -1 or start >= end:
        return None
    return text[start : end + len(ONBOARDING_NAME_MEMORY_END)]

def strip_onboarding_name_markers(text: str) -> str:
    return text.replace(ONBOARDING_NAME_MEMORY_START, "").replace(
        ONBOARDING_NAME_MEMORY_END, ""
    )

def run_onboarding_if_needed(agent_name: str = "opscode") -> None:
    """Run onboarding on interactive terminal if ~/.opscode/{agent}/AGENTS.md is missing."""
    user_md = settings.user_opscode_dir / agent_name / "AGENTS.md"
    if user_md.exists():
        return

    # Check if standard input is interactive
    if not sys.stdin.isatty():
        logger.info("Non-interactive terminal detected; skipping onboarding wizard.")
        return

    print("====================================================")
    print("      Welcome to OpsCode (DevOps Coder) Setup!       ")
    print("====================================================")
    try:
        name = input("Enter your preferred name: ").strip() or "DevOps Engineer"
        provider = input("Preferred LLM Provider (e.g. anthropic, openai): ").strip() or "anthropic"
        cloud = input("Target Cloud (AWS, GCP, Azure, None): ").strip() or "AWS"
        iac = input("IaC Tool Preference (Terraform, Helm, Ansible, None): ").strip() or "Terraform"
    except (KeyboardInterrupt, EOFError):
        print("\nOnboarding aborted. Using default configuration.")
        name, provider, cloud, iac = "DevOps Engineer", "anthropic", "AWS", "Terraform"

    block = _onboarding_name_memory_block(name, provider, cloud, iac)
    try:
        user_md.parent.mkdir(parents=True, exist_ok=True)
        user_md.write_text(f"## User Preferences\n\n{block}\n", encoding="utf-8")
        print(f"Setup complete! Preferences saved to {user_md}")
    except OSError as e:
        logger.error("Failed to write onboarding memory file: %s", e)
