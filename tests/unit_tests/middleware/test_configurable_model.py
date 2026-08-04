"""Tests for the configurable model middleware."""

from __future__ import annotations

import pytest

from dcoder.commands.core.model import ModelHandler
from dcoder.state.session import SessionManager


class TestConfigurableModel:
    @pytest.mark.asyncio
    async def test_model_switch_at_runtime(self, mock_app, make_ctx):
        """/model <provider:name> switches the model mid-conversation."""
        ctx = make_ctx(args="anthropic:claude-3-opus", raw="/model anthropic:claude-3-opus", app=mock_app)
        res = await ModelHandler().execute(ctx)
        
        assert res.success
        mock_app.switch_model.assert_called_once_with("anthropic:claude-3-opus", extra_kwargs={})

    @pytest.mark.asyncio
    async def test_model_switch_interactive(self, mock_app, make_ctx):
        """/model without args shows the selector."""
        ctx = make_ctx(args="", raw="/model", app=mock_app)
        res = await ModelHandler().execute(ctx)
        
        assert res.success
        mock_app._show_model_selector.assert_called_once()
