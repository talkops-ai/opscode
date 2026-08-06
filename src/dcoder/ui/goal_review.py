"""Goal review screen and widget exports."""

from __future__ import annotations

from dcoder.ui.widgets.goal_review import (
    GoalReviewAccepted,
    GoalReviewCancelled,
    GoalReviewEdited,
    GoalReviewMenu,
    GoalReviewRejected,
    GoalReviewResult,
    GoalReviewTextArea,
)
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class GoalReviewScreen(ModalScreen[str]):
    """Legacy Modal for reviewing a proposed goal and rubric.

    Dismiss values:
      - ``"accept"``  — accept the proposed rubric
      - ``"reject"``  — reject and regenerate
      - ``""``        — cancelled (Escape)
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=True),
        Binding("enter", "accept", "Accept", show=True),
    ]

    DEFAULT_CSS = """
    GoalReviewScreen {
        align: center middle;
    }

    GoalReviewScreen > #goal-review-container {
        width: 80;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    GoalReviewScreen > #goal-review-container > #goal-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    GoalReviewScreen > #goal-review-container > #goal-objective {
        color: $text-muted;
        margin-bottom: 1;
        padding: 0 1;
    }

    GoalReviewScreen > #goal-review-container > #rubric-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    GoalReviewScreen > #goal-review-container > #rubric-content {
        color: $text;
        margin-bottom: 1;
        padding: 0 1;
        max-height: 20;
        overflow-y: auto;
    }

    GoalReviewScreen > #goal-review-container > #goal-button-bar {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    GoalReviewScreen > #goal-review-container > #goal-button-bar > Button {
        margin: 0 1;
    }

    GoalReviewScreen > #goal-review-container > #goal-button-bar > #btn-accept {
        background: $success;
    }

    GoalReviewScreen > #goal-review-container > #goal-button-bar > #btn-reject {
        background: $error;
    }

    GoalReviewScreen > #goal-review-container > #goal-button-bar > #btn-cancel {
        background: $surface-darken-2;
    }
    """

    def __init__(
        self,
        objective: str,
        rubric: str,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._objective = objective
        self._rubric = rubric

    def compose(self) -> ComposeResult:
        with Vertical(id="goal-review-container"):
            yield Label("🎯 Goal Review", id="goal-title")
            yield Static(self._objective, id="goal-objective")
            yield Label("Acceptance Criteria:", id="rubric-title")
            yield Static(self._rubric, id="rubric-content")
            with Horizontal(id="goal-button-bar"):
                yield Button("✓ Accept", id="btn-accept", variant="success")
                yield Button("✗ Reject", id="btn-reject", variant="error")
                yield Button("Cancel", id="btn-cancel", variant="default")

    @on(Button.Pressed, "#btn-accept")
    def _on_accept(self, event: Button.Pressed) -> None:
        self.dismiss("accept")

    @on(Button.Pressed, "#btn-reject")
    def _on_reject(self, event: Button.Pressed) -> None:
        self.dismiss("reject")

    @on(Button.Pressed, "#btn-cancel")
    def _on_cancel(self, event: Button.Pressed) -> None:
        self.dismiss("")

    def action_cancel(self) -> None:
        self.dismiss("")

    def action_accept(self) -> None:
        self.dismiss("accept")


__all__ = [
    "GoalReviewAccepted",
    "GoalReviewCancelled",
    "GoalReviewEdited",
    "GoalReviewMenu",
    "GoalReviewRejected",
    "GoalReviewResult",
    "GoalReviewScreen",
    "GoalReviewTextArea",
]
