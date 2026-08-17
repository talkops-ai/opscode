"""Unit tests for Phase 1 TUI Core Infrastructure modules:
- theme.py
- command_registry.py
- message_store.py
- textual_adapter.py
"""

import pytest

from opscode.ui.command_registry import (
    ALWAYS_IMMEDIATE,
    COMMANDS,
    BypassTier,
    SlashCommand,
    build_skill_commands,
    get_command,
)
from opscode.ui.message_store import (
    MessageData,
    MessageStore,
    MessageType,
    ToolStatus,
)
from opscode.ui.theme import (
    DARK_COLORS,
    LIGHT_COLORS,
    ThemeColors,
    get_css_variable_defaults,
    get_registry,
)


def test_theme_colors_validation():
    """Verify ThemeColors raises ValueError on invalid hex colors."""
    assert DARK_COLORS.primary == "#2dd4bf"
    assert LIGHT_COLORS.primary == "#0d9488"

    kwargs = {f.name: getattr(DARK_COLORS, f.name) for f in ThemeColors.__dataclass_fields__.values()}
    kwargs["primary"] = "invalid_hex"

    with pytest.raises(ValueError):
        ThemeColors(**kwargs)



def test_theme_css_defaults():
    """Verify CSS variable defaults generation."""
    defaults = get_css_variable_defaults(dark=True)
    assert defaults["mode-bash"] == DARK_COLORS.mode_bash
    assert defaults["plan-add"] == DARK_COLORS.plan_add
    assert defaults["ctx-prod"] == DARK_COLORS.ctx_prod


def test_theme_registry():
    """Verify built-in theme registration."""
    reg = get_registry()
    assert "opscode-dark" in reg
    assert "opscode-light" in reg
    assert reg["opscode-dark"].colors == DARK_COLORS


def test_command_registry():
    """Verify command registration and bypass tier resolution."""
    assert len(COMMANDS) >= 20
    quit_cmd = get_command("/quit")
    assert quit_cmd is not None
    assert quit_cmd.bypass_tier == BypassTier.ALWAYS

    clear_cmd = get_command("/clear")
    assert clear_cmd is not None
    assert clear_cmd.bypass_tier == BypassTier.QUEUED

    assert "/quit" in ALWAYS_IMMEDIATE
    assert "/force-clear" in ALWAYS_IMMEDIATE


def test_skill_commands():
    """Verify skill command auto-generation."""
    class FakeSkill:
        name = "terraform_expert"
        description = "Terraform IaC Skill"

    skills = [FakeSkill()]
    skill_cmds = build_skill_commands(skills)
    assert len(skill_cmds) == 1
    assert skill_cmds[0].name == "/terraform-expert"


def test_message_store():
    """Verify MessageStore CRUD and thread isolation."""
    store = MessageStore()
    store.append(MessageType.USER, "Hello", thread_id="t1")
    store.append(MessageType.ASSISTANT, "Hi", thread_id="t1")
    store.append(MessageType.USER, "Other", thread_id="t2")

    t1_msgs = store.get_thread("t1")
    t2_msgs = store.get_thread("t2")
    assert len(t1_msgs) == 2
    assert len(t2_msgs) == 1
    assert t1_msgs[0].content == "Hello"
