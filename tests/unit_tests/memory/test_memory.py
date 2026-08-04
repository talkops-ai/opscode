import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest

from dcoder.memory.registry import MemoryRegistry
from dcoder.memory.guard import ManagedMemoryGuardMiddleware
from dcoder.memory.onboarding import (
    ONBOARDING_NAME_MEMORY_START,
    ONBOARDING_NAME_MEMORY_END,
    _onboarding_name_memory_block,
    _upsert_onboarding_name_memory,
)

def test_memory_registry_singleton():
    reg1 = MemoryRegistry.get_instance()
    reg2 = MemoryRegistry.get_instance()
    assert reg1 is reg2

def test_memory_registry_paths():
    reg = MemoryRegistry.get_instance()
    user_paths = reg.get_memory_paths_for_scope("user")
    assert len(user_paths) > 0
    assert any("AGENTS.md" in str(p) for p in user_paths)

def test_resolve_virtual_path_priorities(tmp_path):
    from dcoder.config.settings import settings
    reg = MemoryRegistry.get_instance()
    
    # Mock settings.project_root
    original_project_root = settings.project_root
    try:
        settings.project_root = tmp_path
        
        # When no files exist, it should fallback to .dcoder/AGENTS.md
        fallback = reg.resolve_virtual_path("/memories/project/AGENTS.md")
        assert fallback == tmp_path / ".dcoder" / "AGENTS.md"
        
        # When .agents/AGENTS.md exists, it should resolve to it
        agents_dir = tmp_path / ".agents"
        agents_dir.mkdir(exist_ok=True)
        agents_md = agents_dir / "AGENTS.md"
        agents_md.write_text("content", encoding="utf-8")
        
        resolved = reg.resolve_virtual_path("/memories/project/AGENTS.md")
        assert resolved == agents_md
        
        # When .dcoder/AGENTS.md also exists, it should resolve to it (higher priority)
        dcoder_dir = tmp_path / ".dcoder"
        dcoder_dir.mkdir(exist_ok=True)
        dcoder_md = dcoder_dir / "AGENTS.md"
        dcoder_md.write_text("content", encoding="utf-8")
        
        resolved = reg.resolve_virtual_path("/memories/project/AGENTS.md")
        assert resolved == dcoder_md
    finally:
        settings.project_root = original_project_root

def test_memory_guard_delete_rejection(tmp_path):
    guarded_file = tmp_path / "AGENTS.md"
    block = _onboarding_name_memory_block("Alice", "anthropic", "AWS", "Terraform")
    guarded_file.write_text(f"## Preferences\n\n{block}\n", encoding="utf-8")

    guard = ManagedMemoryGuardMiddleware([guarded_file])
    
    # Mock request using MagicMock
    req = MagicMock()
    req.tool_call = {
        "name": "delete",
        "args": {"file_path": str(guarded_file)},
        "id": "call-123",
    }
    
    # Since it contains the onboarding block, delete should be blocked/rejected
    def dummy_handler(request):
        return ToolMessage(content="Deleted", name="delete", tool_call_id="call-123")

    result = guard.wrap_tool_call(req, dummy_handler)
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert "must not be deleted" in result.content

def test_memory_guard_edit_restoration(tmp_path):
    guarded_file = tmp_path / "AGENTS.md"
    block = _onboarding_name_memory_block("Alice", "anthropic", "AWS", "Terraform")
    initial_content = f"## Preferences\n\n{block}\n"
    guarded_file.write_text(initial_content, encoding="utf-8")

    guard = ManagedMemoryGuardMiddleware([guarded_file])

    # Model tries to edit/clobber the block
    req = MagicMock()
    req.tool_call = {
        "name": "write_file",
        "args": {
            "file_path": str(guarded_file),
            "content": "Clobbered preferences!",
        },
        "id": "call-456",
    }

    def dummy_handler(request):
        # Simulator writes new content to the file
        guarded_file.write_text("Clobbered preferences!", encoding="utf-8")
        return ToolMessage(content="Written", name="write_file", tool_call_id="call-456")

    result = guard.wrap_tool_call(req, dummy_handler)
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert "must not be edited" in result.content

    # The guard should have restored the onboarding block in the file
    restored_content = guarded_file.read_text(encoding="utf-8")
    assert ONBOARDING_NAME_MEMORY_START in restored_content
    assert "Alice" in restored_content
