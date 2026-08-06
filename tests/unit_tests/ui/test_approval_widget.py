"""Unit tests for ApprovalMenu widget and tool renderers."""

import asyncio
import pytest
from dcoder.file_ops import is_sensitive_file_path, format_display_path
from dcoder.ui.tool_renderers import get_renderer
from dcoder.ui.widgets.approval import ApprovalMenu, _is_command_too_long, _truncate_command


def test_sensitive_file_detection():
    """Verify sensitive file path detection logic."""
    assert is_sensitive_file_path(".env")
    assert is_sensitive_file_path(".env.local")
    assert is_sensitive_file_path("/path/to/credentials.json")
    assert is_sensitive_file_path("id_rsa")
    assert is_sensitive_file_path("server.pem")
    assert is_sensitive_file_path("keystore.jks")

    # Non-sensitive files
    assert not is_sensitive_file_path("main.py")
    assert not is_sensitive_file_path("index.html")
    assert not is_sensitive_file_path("config.json")


def test_command_truncation_helpers():
    """Verify command length check and truncation helpers."""
    short_cmd = "ls -la"
    assert not _is_command_too_long(short_cmd)

    long_cmd = "a" * 150
    assert _is_command_too_long(long_cmd)
    truncated = _truncate_command(long_cmd)
    assert truncated.endswith("…") or truncated.endswith("...")

    multiline_cmd = "line1\nline2\nline3\nline4\nline5\nline6"
    assert _is_command_too_long(multiline_cmd)


def test_tool_renderers_registry():
    """Verify tool renderer selection."""
    w_renderer = get_renderer("write_file")
    e_renderer = get_renderer("replace_file_content")
    d_renderer = get_renderer("delete_file")

    widget_cls, data = w_renderer.get_approval_widget({"file_path": "test.txt", "content": "hello"})
    assert data["file_path"] == "test.txt"

    widget_cls_e, data_e = e_renderer.get_approval_widget({"file_path": "test.txt", "old_string": "a", "new_string": "b"})
    assert data_e["file_path"] == "test.txt"


@pytest.mark.asyncio
async def test_approval_menu_approve():
    """Test ApprovalMenu approve decision."""
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    action_req = {"name": "run_command", "call_id": "call-1", "args": {"command": "terraform plan"}}
    menu = ApprovalMenu(action_req)
    menu.set_future(future)

    menu.action_select_approve()
    assert future.done()
    result = future.result()
    assert result["type"] == "approve"


@pytest.mark.asyncio
async def test_approval_menu_auto_approve_toggle():
    """Test ApprovalMenu auto-approve decision (key 'a')."""
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    action_req = {"name": "run_command", "call_id": "call-1", "args": {"command": "terraform plan"}}
    menu = ApprovalMenu(action_req, auto_mode_eligible=True)
    menu.set_future(future)

    menu.action_select_auto()
    assert future.done()
    result = future.result()
    assert result["type"] == "auto_approve_all"


@pytest.mark.asyncio
async def test_approval_menu_reject_with_reason():
    """Test ApprovalMenu rejection with custom reason message."""
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    action_req = {"name": "run_command", "call_id": "call-1", "args": {"command": "terraform destroy"}}
    menu = ApprovalMenu(action_req)
    menu.set_future(future)

    # Select reject and provide reason
    menu._handle_selection(menu._reject_index, reject_message="Do not destroy prod DB")
    assert future.done()
    result = future.result()
    assert result["type"] == "reject"
    assert result["message"] == "Do not destroy prod DB"
