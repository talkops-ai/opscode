from pathlib import Path
import pytest
from dcoder.prompts.resolver import PromptResolver, PromptSlot, PromptContext, create_default_resolver

def test_prompt_resolver(tmp_path):
    template = "Hello {user}! You are running {mode_description}."
    template_file = tmp_path / "sys_prompt.md"
    template_file.write_text(template)

    resolver = PromptResolver(template_file)
    resolver.register_slot(PromptSlot("user", lambda ctx: "DevOps Engineer"))
    resolver.register_slot(PromptSlot("mode_description", lambda ctx: "interactive"))

    ctx = PromptContext(mode="interactive")
    resolved = resolver.resolve(ctx)
    assert resolved == "Hello DevOps Engineer! You are running interactive."


def test_default_resolver_placeholders():
    resolver = create_default_resolver()
    ctx = PromptContext(
        mode="headless",
        model_name="claude-3-5-sonnet",
        model_provider="anthropic",
        working_dir="/fake/dir",
        context_limit=200000,
    )
    resolved = resolver.resolve(ctx)
    assert "headless" in resolved
    assert "claude-3-5-sonnet" in resolved
    assert "/fake/dir" in resolved
    assert "200,000" in resolved
    assert "Terraform" in resolved  # DevOps additions

def test_devops_context_resolved():
    resolver = create_default_resolver()
    ctx = PromptContext()
    resolved = resolver.resolve(ctx)
    assert "Terraform" in resolved or "DevOps" in resolved
