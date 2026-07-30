"""Confirmation modals for package installation in DCoder TUI."""

from __future__ import annotations

import logging
from typing import ClassVar

from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from dcoder.model.config import PROVIDER_DISPLAY_NAMES

logger = logging.getLogger(__name__)


class InstallProviderConfirmScreen(ModalScreen[bool]):
    """Confirmation modal for installing a model provider's extra.

    Shown when the user selects a model whose provider integration package is not installed.
    Dismisses with True to install and False to cancel.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "confirm", "Install", show=False, priority=True),
        Binding("escape", "cancel", "Cancel", show=False, priority=True),
    ]

    CSS = """
    InstallProviderConfirmScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    InstallProviderConfirmScreen > Vertical {
        width: 68;
        max-width: 90%;
        height: auto;
        max-height: 90vh;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    InstallProviderConfirmScreen .install-confirm-title {
        text-style: bold;
        color: $primary;
        text-align: center;
        margin-bottom: 1;
    }

    InstallProviderConfirmScreen .install-confirm-body {
        height: auto;
        color: $text;
        margin-bottom: 1;
    }

    InstallProviderConfirmScreen .install-confirm-help {
        height: 1;
        color: $text-muted;
        text-style: italic;
        text-align: center;
    }
    """

    def __init__(
        self, provider: str, extra: str, model_spec: str | None = None
    ) -> None:
        super().__init__()
        self._provider = provider
        self._extra = extra
        self._model_spec = model_spec

    def compose(self):
        provider_name = PROVIDER_DISPLAY_NAMES.get(
            self._provider, self._provider.replace("_", " ").title()
        )
        if self._model_spec is not None:
            body = (
                f"To use [bold]{self._model_spec}[/bold], dcoder needs to "
                f"install the [bold]{self._extra}[/bold] integration. This will add "
                f"the provider package to your dcoder environment."
            )
        else:
            body = (
                f"To add a key for [bold]{provider_name}[/bold], dcoder needs to "
                f"install the [bold]{self._extra}[/bold] integration. This will add "
                f"the provider package to your dcoder environment."
            )

        with Vertical():
            yield Static(
                f"Install {provider_name} support?",
                classes="install-confirm-title",
            )
            yield Static(
                body,
                classes="install-confirm-body",
                markup=True,
            )
            yield Static(
                "Enter to install, Esc to cancel",
                classes="install-confirm-help",
            )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
