"""Tool-call approval widgets for the DCoder TUI.

Provides low-risk inline approval cards and high-risk full-screen ModalScreen overlays
with diff previews, risk level assessment, and rejection feedback comments.
"""

from __future__ import annotations

from typing import Any, ClassVar

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Static, TextArea, Input

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


class ApprovalMenu(Container):
    """Inline approval card for low/medium risk tool executions."""

    DEFAULT_CSS = """
    ApprovalMenu {
        layout: vertical;
        padding: 1;
        margin: 1 0;
        border: heavy $warning;
        background: $surface;
    }
    ApprovalMenu .approval-title {
        color: $warning;
        text-style: bold;
    }
    ApprovalMenu .approval-scroll {
        height: auto;
        max-height: 15;
    }
    ApprovalMenu .approval-detail {
        margin: 1 0;
        color: $foreground;
    }
    ApprovalMenu .approval-options-container {
        height: auto;
        margin-top: 1;
    }
    ApprovalMenu .approval-option {
        color: $foreground;
    }
    ApprovalMenu .approval-option-selected {
        color: $primary;
        text-style: bold;
    }
    ApprovalMenu .approval-reason-input {
        margin-top: 1;
    }
    ApprovalMenu .approval-help {
        color: $foreground;
        text-style: dim;
        margin-top: 1;
    }
    """

    can_focus = True
    can_focus_children = False

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "move_up", "Up", show=False),
        Binding("k", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("j", "move_down", "Down", show=False),
        Binding("enter", "select", "Select", show=False),
        Binding("1", "select_position(0)", "Select first", show=False),
        Binding("2", "select_position(1)", "Select second", show=False),
        Binding("y", "select_approve", "Approve", show=False),
        Binding("n", "select_reject", "Reject", show=False),
        Binding("tab", "reject_with_reason", "Reject with reason", show=False),
        Binding("escape", "cancel_reason", "Cancel", show=False),
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

        self._options = [
            ("Approve (y)", True),
            ("Reject (n)", False)
        ]
        self._num_options = len(self._options)
        self._selected = 0
        self._option_widgets: list[Static] = []
        
        self._reason_input: Input | None = None
        self._reason_input_active = False
        self._help_widget: Static | None = None

    def compose(self) -> ComposeResult:
        risk_icon = "🟢" if self._risk == "low" else "🟡"
        rendered = render_tool_approval(self._tool_name, self._args)
        title = Text(f"{risk_icon} Approval Required: {rendered.title}", style="bold warning")
        yield Static(title, classes="approval-title")

        with VerticalScroll(classes="approval-scroll"):
            if rendered.diff_lines:
                patch = "\n".join(rendered.diff_lines)
                yield Static(compose_diff_lines(patch))
            elif "patch" in self._args or "diff" in self._args:
                patch = self._args.get("patch") or self._args.get("diff") or ""
                yield Static(compose_diff_lines(patch))
            else:
                lines = rendered.details or [f"{k}: {v}" for k, v in self._args.items() if k != "content"]
                yield Static("\n".join(lines), classes="approval-detail")

        with Container(classes="approval-options-container"):
            for i in range(self._num_options):
                widget = Static("", classes="approval-option")
                self._option_widgets.append(widget)
                yield widget

        self._reason_input = Input(
            placeholder="Reason (Enter to submit, Esc to cancel)",
            classes="approval-reason-input",
            id="approval-reason-input",
        )
        self._reason_input.display = False
        yield self._reason_input

        self._help_widget = Static(self._compose_help_text(), classes="approval-help")
        yield self._help_widget

    def _compose_help_text(self) -> str:
        if self._reason_input_active:
            return "Enter submit • Esc cancel • leave blank to reject without a reason"
        help_parts = ["↑/↓ navigate", "Enter select", "y/n quick keys"]
        if self._selected == 1: # Reject option
            help_parts.append("Tab amend")
        return " • ".join(help_parts)

    def on_mount(self) -> None:
        self._update_options()
        self.focus()

    def _update_options(self) -> None:
        for i, ((text, _), widget) in enumerate(zip(self._options, self._option_widgets)):
            cursor = "> " if i == self._selected else "  "
            widget.update(f"{cursor}{i + 1}. {text}")

            widget.remove_class("approval-option-selected")
            if i == self._selected:
                widget.add_class("approval-option-selected")
                
        if self._help_widget is not None:
            self._help_widget.update(self._compose_help_text())

    def action_move_up(self) -> None:
        if self._reason_input_active:
            return
        self._selected = (self._selected - 1) % self._num_options
        self._update_options()

    def action_move_down(self) -> None:
        if self._reason_input_active:
            return
        self._selected = (self._selected + 1) % self._num_options
        self._update_options()

    def action_select(self) -> None:
        self._handle_selection(self._selected)

    def action_select_position(self, position: int) -> None:
        if not 0 <= position < self._num_options:
            return
        self._handle_selection(position)

    def action_select_approve(self) -> None:
        self._handle_selection(0)

    def action_select_reject(self) -> None:
        if self._reason_input_active:
            self.action_cancel_reason()
            return
        self._handle_selection(1)

    def action_cancel_reason(self) -> None:
        if not self._reason_input_active or self._reason_input is None:
            return
        self._reason_input_active = False
        self._reason_input.display = False
        if self._help_widget is not None:
            self._help_widget.update(self._compose_help_text())
        self.focus()

    def action_reject_with_reason(self) -> None:
        if self._reason_input_active or self._selected != 1:
            return
        if self._reason_input is None:
            return
        self._reason_input_active = True
        self._reason_input.value = ""
        self._reason_input.display = True
        if self._help_widget is not None:
            self._help_widget.update(self._compose_help_text())
        self._reason_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input is not self._reason_input:
            return
        event.stop()
        if not self._reason_input_active:
            return
        reason = event.value.strip()
        self._reason_input_active = False
        self._handle_selection(1, reject_message=reason or None)

    def _handle_selection(self, option: int, *, reject_message: str | None = None) -> None:
        approved = self._options[option][1]
        comment = reject_message if reject_message else ""
        
        self.display = False
        self.post_message(
            ApprovalDecided(
                approved=approved,
                tool_name=self._tool_name,
                call_id=self._call_id,
                comment=comment,
            )
        )
        self.remove()

    def on_blur(self) -> None:
        if self._reason_input_active:
            return
        self.call_after_refresh(self.focus)


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
