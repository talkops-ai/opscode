"""Tests for tool rendering, specific to the UI components (ToolGroupSummary, ToolCallMessage)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from dcoder.ui.messages import (
    _COLLAPSE_OUTPUT_BY_DEFAULT,
    ToolGroupSummary,
    ToolCallMessage,
)
from dcoder.ui.tool_display import format_tool_result_summary


def test_collapse_output_by_default_contains_new_tools():
    """Verify that view_file and list_dir are configured to collapse by default."""
    assert "view_file" in _COLLAPSE_OUTPUT_BY_DEFAULT
    assert "list_dir" in _COLLAPSE_OUTPUT_BY_DEFAULT
    assert "read_file" in _COLLAPSE_OUTPUT_BY_DEFAULT


def test_tool_group_summary_visibility_application():
    """Verify ToolGroupSummary hides its members when collapsed and shows them when expanded."""
    group = ToolGroupSummary()
    # Mock collapsible members
    mock_member1 = MagicMock()
    mock_member2 = MagicMock()
    
    from typing import cast, Any
    group._collapsible = cast(Any, [mock_member1, mock_member2])
    
    # By default it is collapsed
    assert group._collapsed is True
    
    group._apply_visibility()
    
    # Collapsed means display is False
    assert mock_member1.display is False
    assert mock_member2.display is False

    # Toggle to expand
    group.toggle()
    assert group._collapsed is False
    
    group._apply_visibility()
    
    # Expanded means display is True
    assert mock_member1.display is True
    assert mock_member2.display is True


def test_view_file_summary_formatting():
    """Verify that view_file triggers the 'Read X lines' formatting rule in tool_display.py."""
    output_1_line = "Just one line"
    summary_1 = format_tool_result_summary("view_file", output_1_line)
    assert "Read 1 lines" in summary_1 or "Read 1 line" in summary_1

    output_3_lines = "line1\nline2\nline3"
    summary_3 = format_tool_result_summary("view_file", output_3_lines)
    assert "Read 3 lines" in summary_3
