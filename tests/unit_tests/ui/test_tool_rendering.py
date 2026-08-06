"""Tests for tool rendering and tool group lifecycle (ToolGroupSummary, ToolCallMessage, MessageList)."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult

from dcoder.ui.messages import (
    _COLLAPSE_OUTPUT_BY_DEFAULT,
    MessageList,
    ToolCallMessage,
    ToolGroupSummary,
    summarize_tool_group,
)
from dcoder.ui.theme import get_css_variable_defaults, get_theme_colors, register_app_themes
from dcoder.ui.tool_display import format_tool_result_summary


def test_collapse_output_by_default_contains_new_tools():
    """Verify that view_file and list_dir are configured to collapse by default."""
    assert "view_file" in _COLLAPSE_OUTPUT_BY_DEFAULT
    assert "list_dir" in _COLLAPSE_OUTPUT_BY_DEFAULT
    assert "read_file" in _COLLAPSE_OUTPUT_BY_DEFAULT


def test_tool_group_summary_visibility_application():
    """Verify ToolGroupSummary hides its members when collapsed and shows them when expanded."""
    group = ToolGroupSummary()
    mock_member1 = MagicMock()
    mock_member2 = MagicMock()

    group._collapsible = cast(Any, [mock_member1, mock_member2])

    assert group._collapsed is True
    group._apply_visibility()

    assert mock_member1.display is False
    assert mock_member2.display is False

    group.toggle()
    assert group._collapsed is False
    group._apply_visibility()

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


def test_summarize_multi_tool_group_phrasing():
    """Verify multi-tool calls aggregate into a single combined phrase."""
    summary = summarize_tool_group(["list_dir", "read_file"], tense="past")
    assert summary == "Listed 1 directory, read 1 file"


class _TestMessageApp(App[None]):
    def on_mount(self) -> None:
        register_app_themes(self)
        self.theme = "dcoder-dark"

    def get_theme_variable_defaults(self) -> dict[str, str]:
        colors = get_theme_colors(self)
        return get_css_variable_defaults(colors=colors)

    def compose(self) -> ComposeResult:
        yield MessageList(id="messages")


@pytest.mark.asyncio
async def test_messagelist_tool_group_lifecycle():
    """Verify MessageList closes active groups and regroups completed tools cleanly."""
    app = _TestMessageApp()
    async with app.run_test():
        messages = app.query_one("#messages", MessageList)

        messages.add_tool_call("list_dir", "call_1", {"path": "."})
        messages.update_tool_result("call_1", "file1.txt\nfile2.txt", success=True)

        messages.add_tool_call("read_file", "call_2", {"file_path": "file1.txt"})
        messages.update_tool_result("call_2", "hello world", success=True)

        assert messages._active_tool_group is not None

        messages.close_active_tool_group()
        assert messages._active_tool_group is None

        await messages.regroup_completed_tools()
        summaries = list(messages.query(ToolGroupSummary))
        assert len(summaries) == 1
        assert summaries[0]._past_text == "Listed 1 directory, read 1 file"


@pytest.mark.asyncio
async def test_historical_thread_tool_regrouping():
    """Verify that history loading (live=False) folds tool calls into ToolGroupSummary on regroup."""
    app = _TestMessageApp()
    async with app.run_test():
        messages = app.query_one("#messages", MessageList)

        # Simulate historical messages mounted during _load_thread_history
        messages.add_tool_call("list_dir", "hist_1", {"path": "."}, live=False)
        messages.update_tool_result("hist_1", "file1.txt", success=True, live=False)

        messages.add_tool_call("read_file", "hist_2", {"file_path": "README.md"}, live=False)
        messages.update_tool_result("hist_2", "# Readme", success=True, live=False)

        # Before regroup, raw tool call widgets are present without a live group
        assert len(list(messages.query(ToolCallMessage))) == 2
        assert len(list(messages.query(ToolGroupSummary))) == 0

        # Regroup completed tools (as called at the end of _load_thread_history)
        await messages.regroup_completed_tools()
        summaries = list(messages.query(ToolGroupSummary))
        assert len(summaries) == 1
        assert summaries[0]._past_text == "Listed 1 directory, read 1 file"
