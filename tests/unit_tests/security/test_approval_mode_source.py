"""Tests for the unified approval-mode resolution chain.

Covers _approval_mode_source, _resolve_approval_mode, _aresolve_approval_mode,
and the updated _should_interrupt_tool_call with both dict and CLIContextSchema contexts.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch

from dcoder.agent.factory import (
    CLIContextSchema,
    _interrupt_predicate,
    _should_interrupt_tool_call,
)
from dcoder.approval_mode import ApprovalMode, approval_mode_key
from dcoder.security.approval_mode_source import (
    _DecidedMode,
    _LiveLookup,
    _approval_mode_source,
    _aresolve_approval_mode,
    _resolve_approval_mode,
)


# ─── _approval_mode_source ──────────────────────────────────


class TestApprovalModeSource:
    """Test the unified context-inspection function."""

    def test_none_context_returns_manual(self):
        """None context should fail closed to MANUAL."""
        result = _approval_mode_source(None)
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.MANUAL

    def test_unknown_type_returns_manual(self):
        """An arbitrary object context should fail closed to MANUAL."""
        result = _approval_mode_source(42)
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.MANUAL

    # ── Dict contexts ─────────────────────────────────────

    def test_dict_with_approval_mode_key_returns_live_lookup(self):
        """Dict with a valid approval_mode_key returns a _LiveLookup."""
        tid = "test-thread-123"
        key = approval_mode_key(tid)
        ctx = {"approval_mode_key": key, "thread_id": tid}
        result = _approval_mode_source(ctx)
        assert isinstance(result, _LiveLookup)
        assert result.key == key

    def test_dict_with_invalid_key_returns_manual(self):
        """Dict with a malformed key returns MANUAL."""
        ctx = {"approval_mode_key": "wrong-key", "thread_id": "test-thread"}
        result = _approval_mode_source(ctx)
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.MANUAL

    def test_dict_with_approval_mode_auto(self):
        """Dict with approval_mode='auto' and no key returns _DecidedMode(AUTO)."""
        ctx = {"approval_mode": "auto"}
        result = _approval_mode_source(ctx)
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.AUTO

    def test_dict_with_approval_mode_yolo(self):
        """Dict with approval_mode='yolo' and no key returns _DecidedMode(YOLO)."""
        ctx = {"approval_mode": "yolo"}
        result = _approval_mode_source(ctx)
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.YOLO

    def test_dict_with_approval_mode_manual(self):
        """Dict with approval_mode='manual' returns MANUAL."""
        ctx = {"approval_mode": "manual"}
        result = _approval_mode_source(ctx)
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.MANUAL

    def test_dict_legacy_auto_approve_true(self):
        """Dict with only auto_approve=True returns YOLO."""
        ctx = {"auto_approve": True}
        result = _approval_mode_source(ctx)
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.YOLO

    def test_dict_legacy_auto_approve_false(self):
        """Dict with only auto_approve=False returns MANUAL."""
        ctx = {"auto_approve": False}
        result = _approval_mode_source(ctx)
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.MANUAL

    def test_dict_empty_returns_manual(self):
        """Empty dict returns MANUAL."""
        result = _approval_mode_source({})
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.MANUAL

    def test_dict_approval_mode_takes_precedence_over_auto_approve(self):
        """When both approval_mode and auto_approve are present, approval_mode wins."""
        ctx = {"approval_mode": "auto", "auto_approve": True}
        result = _approval_mode_source(ctx)
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.AUTO

    def test_dict_key_takes_precedence_over_approval_mode(self):
        """When approval_mode_key is present, it takes precedence over approval_mode."""
        tid = "test-thread-456"
        key = approval_mode_key(tid)
        ctx = {
            "approval_mode_key": key,
            "thread_id": tid,
            "approval_mode": "auto",
        }
        result = _approval_mode_source(ctx)
        assert isinstance(result, _LiveLookup)
        assert result.key == key

    # ── CLIContextSchema contexts ─────────────────────────

    def test_schema_with_approval_mode_key_returns_live_lookup(self):
        """CLIContextSchema with valid key returns _LiveLookup."""
        tid = "schema-thread-789"
        key = approval_mode_key(tid)
        ctx = CLIContextSchema(
            approval_mode_key=key,
            thread_id=tid,
            approval_mode="auto",
        )
        result = _approval_mode_source(ctx)
        assert isinstance(result, _LiveLookup)
        assert result.key == key

    def test_schema_with_approval_mode_auto(self):
        """CLIContextSchema with approval_mode='auto' and no key returns AUTO."""
        ctx = CLIContextSchema(approval_mode="auto")
        result = _approval_mode_source(ctx)
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.AUTO

    def test_schema_with_approval_mode_yolo(self):
        """CLIContextSchema with approval_mode='yolo' and no key returns YOLO."""
        ctx = CLIContextSchema(approval_mode="yolo")
        result = _approval_mode_source(ctx)
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.YOLO

    def test_schema_with_legacy_auto_approve(self):
        """CLIContextSchema with default manual + auto_approve=True returns YOLO."""
        ctx = CLIContextSchema(auto_approve=True)
        result = _approval_mode_source(ctx)
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.YOLO

    def test_schema_default_returns_manual(self):
        """Default CLIContextSchema returns MANUAL."""
        ctx = CLIContextSchema()
        result = _approval_mode_source(ctx)
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.MANUAL

    def test_schema_approval_mode_takes_precedence_over_auto_approve(self):
        """CLIContextSchema: approval_mode field wins over auto_approve."""
        ctx = CLIContextSchema(approval_mode="auto", auto_approve=True)
        result = _approval_mode_source(ctx)
        assert isinstance(result, _DecidedMode)
        assert result.mode is ApprovalMode.AUTO


# ─── _resolve_approval_mode (sync) ──────────────────────


class TestResolveApprovalMode:
    """Test the synchronous approval-mode resolver."""

    def test_decided_mode_skips_store(self):
        """When source is _DecidedMode, store is never consulted."""
        ctx = {"approval_mode": "auto"}
        mode = _resolve_approval_mode(ctx, store=None)
        assert mode is ApprovalMode.AUTO

    def test_live_lookup_reads_store(self):
        """When source is _LiveLookup, store.get is called."""
        tid = "sync-thread-1"
        key = approval_mode_key(tid)
        ctx = {"approval_mode_key": key, "thread_id": tid}

        mock_store = Mock()
        mock_store.get.return_value = Mock(value={"mode": "yolo"})

        mode = _resolve_approval_mode(ctx, store=mock_store)
        assert mode is ApprovalMode.YOLO
        mock_store.get.assert_called_once()

    def test_live_lookup_store_miss_returns_manual(self):
        """When store returns None for a _LiveLookup, fall back to MANUAL."""
        tid = "sync-thread-2"
        key = approval_mode_key(tid)
        ctx = {"approval_mode_key": key, "thread_id": tid}

        mock_store = Mock()
        mock_store.get.return_value = None

        mode = _resolve_approval_mode(ctx, store=mock_store)
        assert mode is ApprovalMode.MANUAL

    def test_live_lookup_no_store_returns_manual(self):
        """When store is None for a _LiveLookup, fall back to MANUAL."""
        tid = "sync-thread-3"
        key = approval_mode_key(tid)
        ctx = {"approval_mode_key": key, "thread_id": tid}

        mode = _resolve_approval_mode(ctx, store=None)
        assert mode is ApprovalMode.MANUAL


# ─── _aresolve_approval_mode (async) ────────────────────


class TestAResolveApprovalMode:
    """Test the async approval-mode resolver."""

    @pytest.mark.asyncio
    async def test_decided_mode_skips_store(self):
        """Async: _DecidedMode skips store."""
        ctx = {"approval_mode": "yolo"}
        mode = await _aresolve_approval_mode(ctx, store=None)
        assert mode is ApprovalMode.YOLO

    @pytest.mark.asyncio
    async def test_live_lookup_reads_store(self):
        """Async: _LiveLookup reads from store via aget."""
        tid = "async-thread-1"
        key = approval_mode_key(tid)
        ctx = {"approval_mode_key": key, "thread_id": tid}

        mock_store = Mock()
        mock_store.aget = AsyncMock(return_value=Mock(value={"mode": "auto"}))

        mode = await _aresolve_approval_mode(ctx, store=mock_store)
        assert mode is ApprovalMode.AUTO
        mock_store.aget.assert_called_once()

    @pytest.mark.asyncio
    async def test_live_lookup_store_miss_returns_manual(self):
        """Async: store miss falls back to MANUAL."""
        tid = "async-thread-2"
        key = approval_mode_key(tid)
        ctx = {"approval_mode_key": key, "thread_id": tid}

        mock_store = Mock()
        mock_store.aget = AsyncMock(return_value=None)

        mode = await _aresolve_approval_mode(ctx, store=mock_store)
        assert mode is ApprovalMode.MANUAL

    @pytest.mark.asyncio
    async def test_schema_auto_mode(self):
        """Async: CLIContextSchema with approval_mode='auto' returns AUTO."""
        ctx = CLIContextSchema(approval_mode="auto")
        mode = await _aresolve_approval_mode(ctx, store=None)
        assert mode is ApprovalMode.AUTO


# ─── _should_interrupt_tool_call (updated) ───────────────


class TestShouldInterruptUnified:
    """Test _should_interrupt_tool_call with the unified resolution chain."""

    def test_dict_context_auto_mode_no_interrupt(self):
        """AUTO mode via dict context: don't interrupt (auto_mode_enabled=True)."""
        request = Mock(
            state=None,
            runtime=Mock(context={"approval_mode": "auto"}, store=None),
        )
        assert not _should_interrupt_tool_call(request)

    def test_dict_context_auto_mode_disabled(self):
        """AUTO mode with auto_mode_enabled=False: DO interrupt."""
        request = Mock(
            state=None,
            runtime=Mock(context={"approval_mode": "auto"}, store=None),
        )
        assert _should_interrupt_tool_call(request, auto_mode_enabled=False)

    def test_schema_context_auto_mode_no_interrupt(self):
        """AUTO mode via CLIContextSchema: don't interrupt."""
        ctx = CLIContextSchema(approval_mode="auto")
        request = Mock(
            state=None,
            runtime=Mock(context=ctx, store=None),
        )
        assert not _should_interrupt_tool_call(request)

    def test_schema_context_yolo_no_interrupt(self):
        """YOLO mode via CLIContextSchema: don't interrupt."""
        ctx = CLIContextSchema(approval_mode="yolo")
        request = Mock(
            state=None,
            runtime=Mock(context=ctx, store=None),
        )
        assert not _should_interrupt_tool_call(request)

    def test_schema_context_manual_does_interrupt(self):
        """MANUAL mode via CLIContextSchema: DO interrupt."""
        ctx = CLIContextSchema(approval_mode="manual")
        request = Mock(
            state=None,
            runtime=Mock(context=ctx, store=None),
        )
        assert _should_interrupt_tool_call(request)

    def test_schema_default_does_interrupt(self):
        """Default CLIContextSchema: DO interrupt."""
        ctx = CLIContextSchema()
        request = Mock(
            state=None,
            runtime=Mock(context=ctx, store=None),
        )
        assert _should_interrupt_tool_call(request)

    def test_no_runtime_does_interrupt(self):
        """No runtime: DO interrupt."""
        request = Mock(state=None, runtime=None)
        assert _should_interrupt_tool_call(request)

    def test_agents_md_bypass_still_works(self):
        """AGENTS.md bypass works regardless of mode."""
        request = Mock(
            state=None,
            runtime=None,
            action={"args": {"path": "/workspace/.agents/AGENTS.md"}},
        )
        assert not _should_interrupt_tool_call(request)


# ─── _interrupt_predicate ────────────────────────────────


class TestInterruptPredicate:
    """Test the predicate factory."""

    def test_predicate_binds_auto_mode_enabled_true(self):
        """Predicate with auto_mode_enabled=True: AUTO → don't interrupt."""
        pred = _interrupt_predicate(auto_mode_enabled=True)
        request = Mock(
            state=None,
            runtime=Mock(context={"approval_mode": "auto"}, store=None),
        )
        assert not pred(request)

    def test_predicate_binds_auto_mode_enabled_false(self):
        """Predicate with auto_mode_enabled=False: AUTO → DO interrupt."""
        pred = _interrupt_predicate(auto_mode_enabled=False)
        request = Mock(
            state=None,
            runtime=Mock(context={"approval_mode": "auto"}, store=None),
        )
        assert pred(request)

    def test_predicate_yolo_always_passes(self):
        """YOLO passes regardless of auto_mode_enabled."""
        pred_enabled = _interrupt_predicate(auto_mode_enabled=True)
        pred_disabled = _interrupt_predicate(auto_mode_enabled=False)
        request = Mock(
            state=None,
            runtime=Mock(context={"approval_mode": "yolo"}, store=None),
        )
        assert not pred_enabled(request)
        assert not pred_disabled(request)

    def test_predicate_manual_always_interrupts(self):
        """MANUAL always interrupts regardless of auto_mode_enabled."""
        pred_enabled = _interrupt_predicate(auto_mode_enabled=True)
        pred_disabled = _interrupt_predicate(auto_mode_enabled=False)
        request = Mock(
            state=None,
            runtime=Mock(context={"approval_mode": "manual"}, store=None),
        )
        assert pred_enabled(request)
        assert pred_disabled(request)
