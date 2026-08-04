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
