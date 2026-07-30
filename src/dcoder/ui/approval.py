"""Tool-call approval widgets for the DCoder TUI.

Provides low-risk inline approval cards and high-risk full-screen ModalScreen overlays
with diff previews, risk level assessment, and rejection feedback comments.
"""

from __future__ import annotations

from typing import Any, ClassVar

from rich.text import Text
from textual import on
from textual.binding import Binding, BindingType
from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Static, TextArea

from dcoder.ui.diff import compose_diff_lines


def assess_tool_risk(tool_name: str, args: dict[str, Any], is_prod: bool = False) -> str:
    """Assess risk level (low, medium, high) for tool call."""
    if is_prod:
        return "high"
    name = tool_name.lower()
    cmd = str(args.get("command", "")).lower()

    if any(k in name or k in cmd for k in ("destroy", "delete", "apply", "drop", "terminate", "rm -rf")):
        return "high"
    if any(k in name or k in cmd for k in ("write", "replace", "patch", "edit")):
        return "medium"
    return "low"


from dcoder.ui.tool_renderers import render_tool_approval


class ApprovalDecided(Message):
    """Fired when user resolves an approval decision."""

    def __init__(
        self,
        approved: bool,
        tool_name: str,
        call_id: str,
        comment: str = "",
    ) -> None:
        super().__init__()
        self.approved = approved
        self.tool_name = tool_name
        self.call_id = call_id
        self.comment = comment


class ApprovalMenu(Widget):
    """Inline approval card for low/medium risk tool executions."""

    DEFAULT_CSS = """
    ApprovalMenu {
        padding: 1;
        margin: 1 0;
        border: heavy $warning;
        background: $surface;
    }
    ApprovalMenu .approval-title {
        color: $warning;
        text-style: bold;
    }
    ApprovalMenu .approval-detail {
        margin: 1 0;
        color: $foreground;
    }
    ApprovalMenu .comment-area {
        height: 3;
        margin-bottom: 1;
    }
    ApprovalMenu .approval-buttons {
        layout: horizontal;
        height: 3;
    }
    ApprovalMenu Button {
        margin-right: 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "approve", "Approve", show=True),
        Binding("n", "reject", "Reject", show=True),
        Binding("escape", "reject", "Cancel", show=False),
    ]

    def __init__(
        self,
        tool_name: str,
        call_id: str,
        args: dict[str, Any],
        risk: str = "low",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._tool_name = tool_name
        self._call_id = call_id
        self._args = args
        self._risk = risk

    def compose(self):
        risk_icon = "🟢" if self._risk == "low" else "🟡"
        rendered = render_tool_approval(self._tool_name, self._args)
        title = Text(f"{risk_icon} Approval Required: {rendered.title}", style="bold warning")
        yield Static(title, classes="approval-title")

        if rendered.diff_lines:
            patch = "\n".join(rendered.diff_lines)
            yield Static(compose_diff_lines(patch))
        elif "patch" in self._args or "diff" in self._args:
            patch = self._args.get("patch") or self._args.get("diff") or ""
            yield Static(compose_diff_lines(patch))
        else:
            lines = rendered.details or [f"{k}: {v}" for k, v in self._args.items() if k != "content"]
            yield Static("\n".join(lines), classes="approval-detail")

        yield TextArea(placeholder="Optional rejection comment (press Tab to focus)...", id="rejection-comment", classes="comment-area")

        with Container(classes="approval-buttons"):
            yield Button("✓ Approve (y)", variant="success", id="btn-approve")
            yield Button("✗ Reject (n)", variant="error", id="btn-reject")

    @on(Button.Pressed, "#btn-approve")
    def action_approve(self) -> None:
        comment_input = self.query_one("#rejection-comment", TextArea)
        self.post_message(
            ApprovalDecided(
                approved=True,
                tool_name=self._tool_name,
                call_id=self._call_id,
                comment=comment_input.text,
            )
        )
        self.remove()

    @on(Button.Pressed, "#btn-reject")
    def action_reject(self) -> None:
        comment_input = self.query_one("#rejection-comment", TextArea)
        self.post_message(
            ApprovalDecided(
                approved=False,
                tool_name=self._tool_name,
                call_id=self._call_id,
                comment=comment_input.text,
            )
        )
        self.remove()

    def action_toggle_comment(self) -> None:
        comment_input = self.query_one("#rejection-comment", TextArea)
        comment_input.styles.display = "block"
        comment_input.focus()


class ApprovalModalScreen(ModalScreen[ApprovalDecided]):
    """Full-screen modal screen for high-risk / production tool executions."""

    DEFAULT_CSS = """
    ApprovalModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #modal-container {
        width: 70;
        height: auto;
        max-height: 25;
        background: $surface;
        border: double $error;
        padding: 1 2;
    }
    .modal-title {
        color: $error;
        text-style: bold;
        margin-bottom: 1;
    }
    .modal-buttons {
        layout: horizontal;
        height: 3;
        margin-top: 1;
    }
    #modal-args-scroll {
        max-height: 10;
        background: $background;
        border: solid $panel;
        padding: 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [

        Binding("y", "approve", "Approve", show=True),
        Binding("n", "reject", "Reject", show=True),
        Binding("escape", "reject", "Cancel", show=False),
    ]

    def __init__(
        self,
        tool_name: str,
        call_id: str,
        args: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._tool_name = tool_name
        self._call_id = call_id
        self._args = args

    def compose(self):
        rendered = render_tool_approval(self._tool_name, self._args)
        with VerticalScroll(id="modal-container"):
            yield Static("🔴 HIGH RISK / PRODUCTION OPERATION APPROVAL", classes="modal-title")
            yield Static(f"Tool: {rendered.title}", classes="modal-title")
            with VerticalScroll(id="modal-args-scroll"):
                if rendered.diff_lines:
                    patch = "\n".join(rendered.diff_lines)
                    yield Static(compose_diff_lines(patch))
                else:
                    details = rendered.details or [f"{k}: {v}" for k, v in self._args.items()]
                    yield Static("\n".join(details))
            yield TextArea(placeholder="Rejection reason / comments...", id="modal-comment")
            with Container(classes="modal-buttons"):
                yield Button("CONFIRM EXECUTION (y)", variant="error", id="btn-modal-approve")
                yield Button("CANCEL / REJECT (n)", variant="primary", id="btn-modal-reject")

    @on(Button.Pressed, "#btn-modal-approve")
    def action_approve(self) -> None:
        comment = self.query_one("#modal-comment", TextArea).text
        self.dismiss(ApprovalDecided(True, self._tool_name, self._call_id, comment))

    @on(Button.Pressed, "#btn-modal-reject")
    def action_reject(self) -> None:
        comment = self.query_one("#modal-comment", TextArea).text
        self.dismiss(ApprovalDecided(False, self._tool_name, self._call_id, comment))
