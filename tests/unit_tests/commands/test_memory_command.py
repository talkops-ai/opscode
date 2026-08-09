"""Unit tests for /memory and /remember commands and static skill alias filtering."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import pytest

from dcoder.commands.power.memory import MemoryHandler
from dcoder.ui.command_registry import _STATIC_SKILL_ALIASES, build_skill_commands, CommandEntry


class TestMemoryCommand:
    @pytest.mark.asyncio
    async def test_remember_empty_conversation_guard(self, mock_app, make_ctx):
        """/remember with no args on empty session yields user-friendly hint."""
        mock_app._has_conversation_messages = AsyncMock(return_value=False)
        ctx = make_ctx(args="", raw="/remember", app=mock_app)
        
        handler = MemoryHandler()
        res = await handler.execute(ctx)
        
        assert res.success
        assert res.message is not None and "Nothing to remember yet. Start a conversation first" in res.message

    @pytest.mark.asyncio
    async def test_remember_rewrites_to_skill_remember(self, mock_app, make_ctx):
        """/remember with messages rewrites to /skill:remember."""
        mock_app._has_conversation_messages = AsyncMock(return_value=True)
        mock_app._handle_skill_command = AsyncMock()
        ctx = make_ctx(args="", raw="/remember", app=mock_app)
        
        handler = MemoryHandler()
        res = await handler.execute(ctx)
        
        assert res.success
        mock_app._handle_skill_command.assert_called_once_with("/skill:remember")

    @pytest.mark.asyncio
    async def test_remember_with_instruction(self, mock_app, make_ctx):
        """/remember <text> rewrites to /skill:remember <text>."""
        mock_app._handle_skill_command = AsyncMock()
        ctx = make_ctx(
            args="focus on docker setup",
            raw="/remember focus on docker setup",
            app=mock_app,
        )
        
        handler = MemoryHandler()
        res = await handler.execute(ctx)
        
        assert res.success
        mock_app._handle_skill_command.assert_called_once_with(
            "/skill:remember focus on docker setup"
        )

    @pytest.mark.asyncio
    async def test_memory_save_get_delete_clear(self, mock_app, make_ctx, tmp_path):
        """/memory save, get, delete, clear operations manage MemoryStore entries."""
        handler = MemoryHandler()

        with patch("dcoder.commands.power.memory._detect_project_root", return_value=tmp_path):
            # 1. Save
            ctx_save = make_ctx(
                args="save terraform-fmt Use terraform fmt -recursive",
                raw="/memory save terraform-fmt Use terraform fmt -recursive",
                app=mock_app,
            )
            res_save = await handler.execute(ctx_save)
            assert res_save.success
            assert res_save.message is not None and "Memory saved" in res_save.message

            # 2. Get
            ctx_get = make_ctx(
                args="get terraform-fmt",
                raw="/memory get terraform-fmt",
                app=mock_app,
            )
            res_get = await handler.execute(ctx_get)
            assert res_get.success
            assert res_get.message is not None and "Use terraform fmt -recursive" in res_get.message

            # 3. Delete
            ctx_del = make_ctx(
                args="delete terraform-fmt",
                raw="/memory delete terraform-fmt",
                app=mock_app,
            )
            res_del = await handler.execute(ctx_del)
            assert res_del.success
            assert res_del.message is not None and "Deleted memory" in res_del.message

            # Verify get fails after delete
            res_get_after = await handler.execute(ctx_get)
            assert not res_get_after.success
            assert res_get_after.message is not None and "not found" in res_get_after.message

            # 4. Save and Clear
            await handler.execute(ctx_save)
            ctx_clear = make_ctx(
                args="clear",
                raw="/memory clear",
                app=mock_app,
            )
            res_clear = await handler.execute(ctx_clear)
            assert res_clear.success
            assert res_clear.message is not None and "Cleared 1 memory entries" in res_clear.message

    @pytest.mark.asyncio
    async def test_memory_show_and_search(self, mock_app, make_ctx, tmp_path):
        """/memory show and search query across loaded files and store entries."""
        handler = MemoryHandler()

        # Create a mock project AGENTS.md file
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("## Rule: Always run pytest before committing")

        with patch("dcoder.commands.power.memory._detect_project_root", return_value=tmp_path), \
             patch("dcoder.memory.registry.MemoryRegistry.get_memory_paths_for_scope", return_value=[agents_md]):
            
            # Save an entry to store
            ctx_save = make_ctx(
                args="save k8s-ns Use team-env naming format for namespaces",
                raw="/memory save k8s-ns Use team-env naming format for namespaces",
                app=mock_app,
            )
            await handler.execute(ctx_save)

            # Test /memory show
            ctx_show = make_ctx(args="show", raw="/memory show", app=mock_app)
            res_show = await handler.execute(ctx_show)
            assert res_show.success
            assert res_show.message is not None and "Active Memories & Knowledge" in res_show.message
            assert res_show.message is not None and "pytest before committing" in res_show.message
            assert res_show.message is not None and "k8s-ns" in res_show.message

            # Test /memory search (matching query)
            ctx_search = make_ctx(args="search pytest", raw="/memory search pytest", app=mock_app)
            res_search = await handler.execute(ctx_search)
            assert res_search.success
            assert res_search.message is not None and "pytest before committing" in res_search.message

            # Test /memory search (no match)
            ctx_search_none = make_ctx(args="search non-existent-term", raw="/memory search non-existent-term", app=mock_app)
            res_search_none = await handler.execute(ctx_search_none)
            assert res_search_none.success
            assert res_search_none.message is not None and "No memories found matching query" in res_search_none.message

    def test_static_skill_alias_filtering(self):
        """build_skill_commands filters static skill aliases like 'remember' and 'skill-creator'."""
        assert "remember" in _STATIC_SKILL_ALIASES
        assert "skill-creator" in _STATIC_SKILL_ALIASES

        skills = [
            {"name": "remember", "description": "Save context to memory"},
            {"name": "skill-creator", "description": "Create skills"},
            {"name": "terraform-builder", "description": "Build terraform code"},
        ]

        cmds = build_skill_commands(skills)
        cmd_names = [cmd.name for cmd in cmds]

        # Built-in static aliases must be excluded from build_skill_commands
        assert "/remember" not in cmd_names
        assert "/skill-creator" not in cmd_names
        assert "/terraform-builder" in cmd_names
