"""Unit tests for Phase 3 Safety & HITL modules:
- approval.py
- ask_user.py
- toast.py & notification_center.py
"""

from dcoder.ui.approval import (
    ApprovalDecided,
    ApprovalMenu,
    assess_tool_risk,
)
from dcoder.ui.ask_user import AskQuestion, AskUserMenu
from dcoder.ui.notification_center import NotificationCenter


def test_assess_tool_risk():
    """Verify tool risk assessment helper."""
    assert assess_tool_risk("terraform_apply", {}, is_prod=True) == "high"
    assert assess_tool_risk("terraform_destroy", {}) == "high"
    assert assess_tool_risk("file_edit", {}) == "medium"
    assert assess_tool_risk("read_file", {}) == "low"


def test_ask_user_menu_structure():
    """Verify AskUserMenu composition with questions."""
    q1 = AskQuestion(id="q1", question="Select env?", options=["dev", "prod"])
    q2 = AskQuestion(id="q2", question="Enter cluster name?")

    menu = AskUserMenu([q1, q2])
    assert len(menu._questions) == 2
    assert menu._questions[0].options == ["dev", "prod"]


def test_notification_center():
    """Verify NotificationCenter storage."""
    nc = NotificationCenter()
    item = nc.add_notification("Title", "Message", severity="warning")
    assert item.title == "Title"
    assert item.severity == "warning"
    assert len(nc._notifications) == 1
