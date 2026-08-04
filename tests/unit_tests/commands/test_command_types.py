"""Unit tests for command surface types and enums."""

import pytest

from dcoder.commands._types import BypassTier, CommandCategory, SafetyLevel
from dcoder.ui.command_registry import BypassTier as RegistryBypassTier


def test_safety_level_values():
    """Verify SafetyLevel enum values match architecture specifications."""
    assert SafetyLevel.READ_ONLY == "read_only"
    assert SafetyLevel.LOW_RISK == "low_risk"
    assert SafetyLevel.HIGH_RISK == "high_risk"
    assert SafetyLevel.DESTRUCTIVE == "destructive"
    assert len(SafetyLevel) == 4


def test_bypass_tier_reexport():
    """Verify BypassTier imported from command framework is identical to command registry."""
    assert BypassTier is RegistryBypassTier
    assert BypassTier.ALWAYS == "always"
    assert BypassTier.QUEUED == "queued"


def test_command_category_values():
    """Verify CommandCategory enum values."""
    assert CommandCategory.CORE == "core"
    assert CommandCategory.POWER == "power"
    assert CommandCategory.DEVOPS == "devops"
    assert CommandCategory.AUTOMATION == "automation"
    assert len(CommandCategory) == 4
