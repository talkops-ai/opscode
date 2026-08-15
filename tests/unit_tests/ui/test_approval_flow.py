import pytest
import os
import json
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock, PropertyMock
from datetime import datetime

from dcoder.mcp.discovery import MCPDiscovery
from dcoder.mcp.session_manager import MCPSessionManager
from dcoder.mcp.trust import (
    is_project_mcp_trusted,
    trust_project_mcp,
    revoke_project_mcp_trust,
    compute_config_fingerprint,
)
from dcoder.backend.sandbox.config import SandboxConfig
from dcoder.backend.sandbox.registry import SandboxRegistry
from dcoder.backend.sandbox.factory import create_sandbox
from dcoder.security.unicode_security import check_url_safety, sanitize_control_chars
from dcoder.security.shell_safety import is_shell_command_allowed
from dcoder.security.approval_mode import approval_mode_key, approval_mode_payload
from dcoder.state.session import SessionManager
from dcoder.middleware.resume_state import ResumeStateMiddleware
from langchain_core.messages import AIMessage


def test_mcp_discovery_precedence(tmp_path):
    global_dir = tmp_path / "global"
    user_dir = tmp_path / "user"
    project_dir = tmp_path / "project"

    global_dir.mkdir()
    user_dir.mkdir()
    project_dir.mkdir()

    # Create mock configurations
    global_cfg = {"mcpServers": {"server1": {"command": "global"}}}
    user_cfg = {"mcpServers": {"server1": {"command": "user"}, "server2": {"command": "user2"}}}
    project_cfg = {"mcpServers": {"server1": {"command": "project"}}}

    global_cfg_dir = global_dir.parent / ".agents"
    global_cfg_dir.mkdir(exist_ok=True)
    (global_cfg_dir / "mcp.json").write_text(json.dumps(global_cfg))
    (user_dir / "mcp.json").write_text(json.dumps(user_cfg))
    (project_dir / ".mcp.json").write_text(json.dumps(project_cfg))

    with patch("dcoder.config.paths.AGENTS_SHARED_DIR", global_dir.parent / ".agents"), \
         patch("dcoder.config.paths.DATA_DIR", user_dir), \
         patch("dcoder.config.paths.GLOBAL_MCP_PATH", user_dir / ".mcp.json"):
        discovery = MCPDiscovery()
        merged = discovery.discover(project_root=project_dir)
        servers = merged
        print("MOCKED HOME:", Path.home())
        print("SERVERS:", servers)
        assert "server1" in servers
        assert servers["server1"].get("command") == "project"
        assert servers["server2"].get("command") == "user2"


def test_mcp_trust_store(tmp_path):
    trust_file = tmp_path / "mcp_trust.json"
    
    cfg_file = tmp_path / ".mcp.json"
    cfg_file.write_text(json.dumps({"mcpServers": {}}))
    fingerprint = compute_config_fingerprint([cfg_file])

    with patch("dcoder.mcp.trust._default_store_path", return_value=trust_file):
        assert not is_project_mcp_trusted("/some/project/root", fingerprint)
        trust_project_mcp("/some/project/root", fingerprint)
        assert is_project_mcp_trusted("/some/project/root", fingerprint)
        revoke_project_mcp_trust("/some/project/root")
        assert not is_project_mcp_trusted("/some/project/root", fingerprint)


def test_shell_safety_validation():
    # Safe commands
    allow_list = ["terraform plan", "git commit", "kubectl get pods"]
    assert is_shell_command_allowed("terraform plan", allow_list)
    assert is_shell_command_allowed("terraform plan -out=tfplan", allow_list)
    assert is_shell_command_allowed("git commit -m 'test'", allow_list)
    
    # Dangerous commands / patterns
    assert not is_shell_command_allowed("terraform plan; rm -rf /", allow_list)
    assert not is_shell_command_allowed("git commit && rm -rf /", allow_list)
    assert not is_shell_command_allowed("terraform plan $(whoami)", allow_list)
    assert not is_shell_command_allowed("terraform plan &", allow_list)
    assert not is_shell_command_allowed("terraform plan $VAR", allow_list)


def test_unicode_security_check():
    # Safe URL
    res = check_url_safety("https://google.com")
    assert res.safe

    # Deceptive URL containing Cyrillic homoglyph 'а'
    res_deceptive = check_url_safety("https://gооgle.com")
    assert not res_deceptive.safe
    assert len(res_deceptive.warnings) > 0


def test_resume_state_middleware():
    middleware = ResumeStateMiddleware()
    
    from langchain_core.messages.ai import UsageMetadata
    from typing import cast
    from dcoder.middleware.resume_state import ResumeState
    
    # AI Message with usage metadata
    msg = AIMessage(
        content="Hello",
        usage_metadata=UsageMetadata({"input_tokens": 10, "output_tokens": 20, "total_tokens": 30})
    )
    state = cast(ResumeState, {"messages": [msg]})
    
    update = middleware.after_model(state, MagicMock())
    assert update == {"_context_tokens": 30}


@pytest.mark.asyncio
async def test_dcoder_app_request_approval_shell_allow_list(monkeypatch):
    """Verify that shell commands on the allow-list are auto-approved without prompting."""
    from dcoder.ui.app import DCoderApp

    app = DCoderApp()
    app._shell_allow_list = ["terraform plan", "git status"]

    mounted = []

    class MockMessageList:
        async def mount(self, widget):
            mounted.append(widget)

    monkeypatch.setattr(app, "query_one", lambda selector, expect_type=None: MockMessageList())

    action_requests = [
        {"name": "run_command", "args": {"command": "terraform plan"}}
    ]

    future = await app._request_approval(action_requests)
    assert future.done()
    assert (await future)["type"] == "approve"
    assert len(mounted) == 1
    assert "Auto-approved shell command" in mounted[0]._raw_content


@pytest.mark.asyncio
async def test_dcoder_app_request_approval_spinner_and_subagent_pause_lifecycle(monkeypatch):
    """Verify loading spinner and subagent panel are paused during approval and resumed after decision."""
    from dcoder.ui.app import DCoderApp

    app = DCoderApp()
    pause_called = []
    resume_called = []

    mock_loading = MagicMock()
    mock_loading.pause = lambda: pause_called.append("spinner")
    mock_loading.resume = lambda: resume_called.append("spinner")
    app._loading_widget = mock_loading

    mock_subagent_panel = MagicMock()
    mock_subagent_panel.pause = lambda: pause_called.append("subagent")
    mock_subagent_panel.resume = lambda: resume_called.append("subagent")
    monkeypatch.setattr(app, "_get_subagent_panel", lambda: mock_subagent_panel)

    class MockMessageList:
        def mount_inline_prompt(self, menu):
            pass

    monkeypatch.setattr(app, "query_one", lambda selector, expect_type=None: MockMessageList())
    monkeypatch.setattr(app, "call_after_refresh", lambda func: None)

    future = await app._request_approval([{"name": "write_file", "args": {"file_path": "test.txt"}}])
    assert "spinner" in pause_called
    assert "subagent" in pause_called

    # Resolve future
    future.set_result({"type": "approve"})
    # Wait small microtick for callback
    await asyncio.sleep(0.01)

    assert "spinner" in resume_called
    assert "subagent" in resume_called


@pytest.mark.asyncio
async def test_dcoder_app_on_approval_menu_decided_auto_mode_switch(monkeypatch):
    """Verify that auto_approve_all decision switches approval mode to AUTO."""
    from dcoder.ui.app import DCoderApp
    from dcoder.approval_mode import ApprovalMode
    from dcoder.ui.widgets.approval import ApprovalMenu

    app = DCoderApp()
    mode_set = None

    async def mock_set_approval_mode(mode):
        nonlocal mode_set
        mode_set = mode
        return True

    monkeypatch.setattr(app, "_set_approval_mode", mock_set_approval_mode)
    monkeypatch.setattr(app, "_focus_chat_input_after_refresh", lambda: None)

    event = ApprovalMenu.Decided(
        decision={"type": "auto_approve_all"},
        approved=True,
        tool_name="run_command",
        call_id="call-auto",
        comment="",
    )

    await app._on_approval_menu_decided(event)
    assert mode_set == ApprovalMode.AUTO

