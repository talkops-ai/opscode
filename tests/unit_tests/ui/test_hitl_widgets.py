"""Unit tests for Phase 3 Safety & HITL modules:
- approval.py
- ask_user.py
- toast.py & notification_center.py
"""

from dcoder.ui.widgets.approval import (
    ApprovalDecided,
    ApprovalMenu,
    assess_tool_risk,
)
from dcoder.ui.widgets.ask_user import AskUserMenu
from dcoder.ui.widgets._ask_user_types import Question
from dcoder.ui.widgets.notification_center import NotificationCenter


import pytest


def test_assess_tool_risk():
    """Verify tool risk assessment helper."""
    assert assess_tool_risk("terraform_apply", {}, is_prod=True) == "high"
    assert assess_tool_risk("terraform_destroy", {}) == "high"
    assert assess_tool_risk("file_edit", {}) == "medium"
    assert assess_tool_risk("read_file", {}) == "low"





def test_notification_center():
    """Verify NotificationCenter storage."""
    nc = NotificationCenter()
    item = nc.add_notification("Title", "Message", severity="warning")
    assert item is not None
    assert item.title == "Title"
    assert item.severity == "warning"
    assert len(nc._notifications) == 1
