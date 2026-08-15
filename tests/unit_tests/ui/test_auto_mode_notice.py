"""Unit tests for AutoModeNoticeScreen Textual modal widget."""

from __future__ import annotations

import pytest
from dcoder.ui.widgets.auto_mode_notice import AutoModeNoticeScreen


def test_auto_mode_notice_screen_initialization():
    screen = AutoModeNoticeScreen()
    assert screen._body is not None
    assert "You switched to **Auto**" in screen._body
    assert screen.can_focus is True


def test_auto_mode_notice_screen_custom_body():
    custom_body = "Custom auto notice body."
    screen = AutoModeNoticeScreen(body=custom_body)
    assert screen._body == custom_body


@pytest.mark.asyncio
async def test_auto_mode_notice_actions(monkeypatch: pytest.MonkeyPatch):
    screen = AutoModeNoticeScreen()
    dismiss_result = []

    def mock_dismiss(result: bool | None = None) -> None:
        dismiss_result.append(result)

    monkeypatch.setattr(screen, "dismiss", mock_dismiss)

    screen.action_confirm()
    assert dismiss_result == [True]

    dismiss_result.clear()
    screen.action_cancel()
    assert dismiss_result == [False]
