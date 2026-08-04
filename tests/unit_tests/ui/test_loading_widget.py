"""Unit tests for LoadingWidget & Spinner matching reference dcode implementation."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from dcoder.ui.loading import LoadingWidget, Spinner, format_duration


class DummyLoadingApp(App[None]):
    """Test app hosting LoadingWidget."""

    def compose(self) -> ComposeResult:
        yield LoadingWidget("Thinking")


def test_spinner_frames_advancement() -> None:
    """Verify Spinner advances frames and loops."""
    spinner = Spinner()
    f1 = spinner.current_frame()
    f2 = spinner.next_frame()
    assert f1 == f2
    f3 = spinner.next_frame()
    assert f3 != f2


def test_format_duration() -> None:
    """Verify format_duration helper outputs human readable time."""
    assert format_duration(5) == "5s"
    assert format_duration(60) == "1m"
    assert format_duration(125) == "2m 5s"


@pytest.mark.asyncio
async def test_loading_widget_lifecycle() -> None:
    """Verify LoadingWidget mount, status update, pause, resume, and unmount."""
    app = DummyLoadingApp()
    async with app.run_test():
        widget = app.query_one(LoadingWidget)
        assert widget._status == "Thinking"
        assert widget._paused is False

        # Status update
        widget.set_status("Executing tool")
        assert widget._status == "Executing tool"
        if widget._status_widget:
            renderable = widget._status_widget.render()
            plain = getattr(renderable, "plain", str(renderable))
            assert "Executing tool" in plain

        # Pause
        widget.pause("Awaiting approval")
        assert widget._paused is True
        assert widget._status == "Awaiting approval"

        # Resume
        widget.resume()
        assert widget._paused is False
        assert widget._status == "Thinking"
