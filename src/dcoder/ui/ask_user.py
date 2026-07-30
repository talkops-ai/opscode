"""AskUser interactive prompt menu for DCoder agent interactions.

Renders multi-question requests from agent (multiple-choice or free-text)
styled with green accent border.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from rich.text import Text
from textual import on
from textual.binding import Binding, BindingType
from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, OptionList, Static, TextArea
from textual.widgets.option_list import Option


@dataclass
class AskQuestion:
    id: str
    question: str
    options: list[str] | None = None
    is_multi_select: bool = False


class AskUserResponse(Message):
    """Fired when user completes and submits answers to AskUserMenu."""

    def __init__(self, answers: dict[str, Any]) -> None:
        super().__init__()
        self.answers = answers


class AskUserMenu(Widget):
    """Multi-question interactive menu for agent clarification requests."""

    DEFAULT_CSS = """
    AskUserMenu {
        padding: 1 2;
        margin: 1 0 0 2;
        background: $surface;
        border: tall $success;
    }
    AskUserMenu .title {
        color: $success;
        text-style: bold;
        margin-bottom: 1;
    }
    AskUserMenu .question-text {
        color: $foreground;
        margin-top: 1;
    }
    AskUserMenu OptionList {
        max-height: 6;
        margin-top: 1;
    }
    AskUserMenu TextArea {
        height: 3;
        margin-top: 1;
    }
    AskUserMenu .buttons {
        layout: horizontal;
        height: 3;
        margin-top: 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+s", "submit", "Submit Answers", show=True),
    ]

    def __init__(
        self, questions: list[AskQuestion], **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self._questions = questions
        self._answers: dict[str, Any] = {}

    def compose(self):
        yield Static("❓ Agent Clarification Needed", classes="title")
        with VerticalScroll():
            for idx, q in enumerate(self._questions):
                prefix = "[Multi-select] " if q.is_multi_select else ""
                yield Static(f"Q{idx+1}: {prefix}{q.question}", classes="question-text")

                if q.options:
                    option_list = OptionList(id=f"opts-{q.id}")
                    for opt in q.options:
                        option_list.add_option(Option(opt))
                    yield option_list
                else:
                    yield TextArea(placeholder="Type your response...", id=f"input-{q.id}")


        with Container(classes="buttons"):
            yield Button("Submit Answers (Ctrl+S)", variant="success", id="btn-submit")

    @on(Button.Pressed, "#btn-submit")
    def action_submit(self) -> None:
        for q in self._questions:
            if q.options:
                opt_list = self.query_one(f"#opts-{q.id}", OptionList)
                if opt_list.highlighted is not None:
                    option = opt_list.get_option_at_index(opt_list.highlighted)
                    self._answers[q.id] = str(option.prompt)
            else:
                text_input = self.query_one(f"#input-{q.id}", TextArea)
                self._answers[q.id] = text_input.text

        self.post_message(AskUserResponse(self._answers))
        self.remove()
