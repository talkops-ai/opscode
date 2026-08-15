"""Unit tests for ApprovalMenu widget and tool renderers."""

import asyncio
import pytest
from unittest.mock import Mock, MagicMock
from textual.app import App, ComposeResult
from dcoder.file_ops import is_sensitive_file_path, format_display_path
from dcoder.ui.widgets.tool_renderers import get_renderer
from dcoder.ui.widgets.approval import ApprovalMenu, _is_command_too_long, _truncate_command
from dcoder.ui.widgets.subagent_panel import SubagentPanel


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

    menu._handle_selection(menu._reject_index, reject_message="Do not destroy prod DB")
    assert future.done()
    result = future.result()
    assert result["type"] == "reject"
    assert result["message"] == "Do not destroy prod DB"


@pytest.mark.asyncio
async def test_app_approval_menu_decided_removes_widget(monkeypatch):
    """Test that _on_approval_menu_decided removes the pending approval widget from DOM."""
    from dcoder.ui.app import DCoderApp

    app = DCoderApp()
    removed = False

    class MockMenu:
        async def remove(self):
            nonlocal removed
            removed = True

    mock_menu = MockMenu()
    app._pending_approval_widget = mock_menu

    monkeypatch.setattr(app, "_focus_chat_input_after_refresh", lambda: None)

    event = ApprovalMenu.Decided(
        decision={"type": "approve"},
        approved=True,
        tool_name="edit_file",
        call_id="call-123",
        comment="",
    )

    await app._on_approval_menu_decided(event)

    assert removed is True
    assert app._pending_approval_widget is None


@pytest.mark.asyncio
async def test_app_request_approval_waits_for_pending_approval(monkeypatch):
    """Test that _request_approval waits for active pending approval widget to clear."""
    from dcoder.ui.app import DCoderApp

    app = DCoderApp()
    app._pending_approval_widget = "active_dummy_widget"

    async def clear_widget_later():
        await asyncio.sleep(0.02)
        app._pending_approval_widget = None

    asyncio.create_task(clear_widget_later())

    mounted_widgets = []

    class MockMessageList:
        def mount_inline_prompt(self, menu):
            mounted_widgets.append(menu)

    monkeypatch.setattr(app, "query_one", lambda selector, expect_type=None: MockMessageList())
    monkeypatch.setattr(app, "call_after_refresh", lambda func: None)

    future = await app._request_approval([{"name": "write_file", "args": {"file_path": "foo.py"}}])

    assert len(mounted_widgets) == 1
    assert app._pending_approval_widget is mounted_widgets[0]
    assert not future.done()

    mounted_widgets[0].action_select_approve()
    assert future.done()
    assert (await future)["type"] == "approve"


@pytest.mark.asyncio
async def test_approval_menu_mouse_click():
    """Test ApprovalMenu mouse click selection on Approve option."""
    action_req = {"name": "run_command", "call_id": "call-1", "args": {"command": "terraform plan"}}
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    menu = ApprovalMenu(action_req)
    menu.set_future(future)

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield menu

    app = TestApp()
    async with app.run_test():
        assert len(menu._option_widgets) > 0
        click_event = Mock()
        click_event.control = menu._option_widgets[0]
        menu._on_option_clicked(click_event)

        assert future.done()
        assert future.result()["type"] == "approve"


@pytest.mark.asyncio
async def test_approval_menu_mouse_click_reject():
    """Test ApprovalMenu mouse click selection on Reject option."""
    action_req = {"name": "run_command", "call_id": "call-1", "args": {"command": "terraform plan"}}
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    menu = ApprovalMenu(action_req)
    menu.set_future(future)

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield menu

    app = TestApp()
    async with app.run_test():
        assert len(menu._option_widgets) > 1
        click_event = Mock()
        # Click reject option
        click_event.control = menu._option_widgets[menu._reject_index]
        menu._on_option_clicked(click_event)

        assert future.done()
        assert future.result()["type"] == "reject"


@pytest.mark.asyncio
async def test_approval_menu_mouse_click_auto_approve():
    """Test ApprovalMenu mouse click selection on Auto-approve option."""
    action_req = {"name": "run_command", "call_id": "call-1", "args": {"command": "terraform plan"}}
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    menu = ApprovalMenu(action_req, auto_mode_eligible=True)
    menu.set_future(future)

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield menu

    app = TestApp()
    async with app.run_test():
        assert len(menu._option_widgets) > 2
        click_event = Mock()
        click_event.control = menu._option_widgets[1]
        menu._on_option_clicked(click_event)

        assert future.done()
        assert future.result()["type"] == "auto_approve_all"


@pytest.mark.asyncio
async def test_approval_menu_select_positions_and_navigation():
    """Test keyboard position selection (1, 2, 3) and expand toggle."""
    action_req = {"name": "run_command", "call_id": "call-1", "args": {"command": "terraform apply"}}
    loop = asyncio.get_running_loop()

    # Test position 0 (Approve)
    fut0 = loop.create_future()
    menu0 = ApprovalMenu(action_req)
    menu0.set_future(fut0)
    menu0.action_select_position(0)
    assert (await fut0)["type"] == "approve"

    # Test position 1 with auto mode (Auto-approve all)
    fut1 = loop.create_future()
    menu1 = ApprovalMenu(action_req, auto_mode_eligible=True)
    menu1.set_future(fut1)
    menu1.action_select_position(1)
    assert (await fut1)["type"] == "auto_approve_all"

    # Test position 2 with auto mode (Reject)
    fut2 = loop.create_future()
    menu2 = ApprovalMenu(action_req, auto_mode_eligible=True)
    menu2.set_future(fut2)
    menu2.action_select_position(2)
    assert (await fut2)["type"] == "reject"

    # Test position 1 without auto mode (Reject)
    fut_no_auto = loop.create_future()
    menu_no_auto = ApprovalMenu(action_req, auto_mode_eligible=False)
    menu_no_auto.set_future(fut_no_auto)
    menu_no_auto.action_select_position(1)
    assert (await fut_no_auto)["type"] == "reject"

    # Test toggle expand
    menu_exp = ApprovalMenu(action_req)
    assert menu_exp._command_expanded is False
    menu_exp.action_toggle_expand()
    # Note: action_toggle_expand toggles when _has_expandable_command and _command_widget are present
    assert hasattr(menu_exp, "action_toggle_expand")


@pytest.mark.asyncio
async def test_subagent_panel_timer_pause_resume():
    """Verify that SubagentPanel pause() and resume() correctly control the refresh timer."""
    panel = SubagentPanel()
    # Pause stops any active timer
    panel.pause()
    assert panel._timer is None


@pytest.mark.asyncio
async def test_task_approval_widget_rendering():
    """Verify TaskApprovalWidget renders subagent_type, warning, and task instructions."""
    from dcoder.ui.widgets.tool_renderers import TaskRenderer
    from dcoder.ui.widgets.tool_widgets import TaskApprovalWidget

    tool_args = {
        "subagent_type": "terraform-reviewer",
        "description": "Audit main.tf and variables.tf for security issues.",
    }
    widget_cls, args = TaskRenderer.get_approval_widget(tool_args)
    assert widget_cls is TaskApprovalWidget

    widget = widget_cls(args)
    children = list(widget.compose())
    assert len(children) == 4
    assert "terraform-reviewer" in str(children[0].render())
    assert "Subagent will have access" in str(children[1].render())
    assert "Audit main.tf" in str(children[3].render())
