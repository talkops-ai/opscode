"""DCoder Textual TUI application orchestrator.

Composes widget tree, manages theme registration, input routing via InputMode,
message queueing with bypass tiers, event routing via TextualAdapter, shell
command execution, and modal overlays.

Architecture (dcode alignment):
    Input flow: ``on_chat_input_submitted`` → ``_submit_input(value, mode)``
    → ``_process_message(value, mode)`` which routes to:
      - ``_handle_command(value)`` for slash commands (synchronous)
      - ``_handle_user_message(value)`` for agent prompts (spawns ONE worker)
      - ``_handle_shell_command(cmd)`` for ``!`` prefixed shell commands

    Only ``_run_agent_task`` and ``_run_shell_task`` spawn workers.
    ``_cleanup_agent_task`` always drains the queue in its ``finally`` block.

Server startup is deferred: the TUI renders immediately with a "Connecting..."
status, then a background worker starts the LangGraph server subprocess.  Once
the server is healthy the ``ServerReady`` message fires and the app binds the
client to the adapter, enabling agent prompts.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.css.query import NoMatches
from textual.message import Message
from textual.theme import Theme

from dcoder.ui.approval import (
    ApprovalDecided,
    ApprovalMenu,
    ApprovalModalScreen,
    assess_tool_risk,
)
from dcoder.ui.autocomplete import AutocompletePopup
from dcoder.ui.chat_input import ChatInput, InputMode
from dcoder.ui.command_registry import (
    ALWAYS_IMMEDIATE,
    IMMEDIATE_UI_CMDS,
    BypassTier,
    get_command,
)
from dcoder.ui.infra_panel import InfraStatePanel
from dcoder.ui.messages import (
    AssistantMessage,
    ErrorMessage,
    MessageList,
    QueuedUserMessage,
    SystemMessage,
    UserMessage,
)
from dcoder.ui.notification_center import NotificationCenter
from dcoder.ui.status import StatusBar
from dcoder.ui.subagent_panel import SubagentPanel
from dcoder.ui.textual_adapter import TextualAdapter
from dcoder.ui.theme import (
    DARK_COLORS,
    LIGHT_COLORS,
    get_css_variable_defaults,
    get_registry,
    load_theme_preference,
    register_app_themes,
    save_theme_preference,
)
from dcoder.ui.theme_selector import ThemeSelectorScreen
from dcoder.ui.toast import show_toast
from dcoder.ui.welcome import WelcomeBanner

from dcoder.ui.permission_store import PermissionStore, load_permission_store



logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────

_TYPING_IDLE_THRESHOLD_SECONDS = 2.0
"""Approval widgets wait this long after the last keystroke before showing."""

_SHELL_TIMEOUT_SECONDS = 60
"""Maximum time a shell command is allowed to run before being killed."""


def _monotonic() -> float:
    """Monotonic clock shortcut."""
    return time.monotonic()


def _format_error_detail(err: Exception) -> str:
    """Extract clean error text from Exception objects or dict representations."""
    if err.args and isinstance(err.args[0], dict):
        d = err.args[0]
        msg = d.get("message") or d.get("error")
        err_type = d.get("error") if d.get("message") else None
        if msg:
            return f"{err_type}: {msg}" if err_type and err_type != str(msg) else str(msg)

    err_str = str(err)
    if "RemoteException(" in err_str or (err_str.startswith("{") and "error" in err_str):
        import ast
        try:
            inner = err_str.split("RemoteException(")[-1].rstrip(")") if "RemoteException(" in err_str else err_str
            parsed = ast.literal_eval(inner)
            if isinstance(parsed, dict):
                msg = parsed.get("message") or parsed.get("error")
                err_type = parsed.get("error") if parsed.get("message") else None
                if msg:
                    return f"{err_type}: {msg}" if err_type and err_type != str(msg) else str(msg)
        except Exception:
            pass
    return err_str



# ── Queued Message ───────────────────────────────────────

@dataclass
class QueuedMessage:
    """A message queued for processing when the app is busy."""

    text: str
    mode: InputMode = "normal"


# ── App ──────────────────────────────────────────────────


class DCoderApp(App):
    """DCoder interactive TUI — DevOps coding agent orchestrator."""

    CSS_PATH = "app.tcss"
    ENABLE_COMMAND_PALETTE = False

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "interrupt", "Cancel", show=False),
        Binding("ctrl+d", "quit_app", "Quit", show=False),
        Binding("ctrl+l", "clear_chat", "Clear", show=False),
        Binding("shift+tab", "toggle_auto_approve", "Auto-approve", show=False),
    ]

    # ── App-level Lifecycle Messages ─────────────────────

    class ServerReady(Message):
        """Posted by ``_start_server_background`` when the server is healthy."""

        def __init__(self, client: Any, server_proc: Any) -> None:
            super().__init__()
            self.client = client
            self.server_proc = server_proc

    class ServerStartFailed(Message):
        """Posted by ``_start_server_background`` on startup failure."""

        def __init__(self, error: Exception) -> None:
            super().__init__()
            self.error = error

    # ── Constructor ──────────────────────────────────────

    def __init__(
        self,
        *,
        assistant_id: str = "dcoder",
        client: Any = None,
        server: Any = None,
        model: str | None = None,
        auto_approve: bool = False,
        resume_thread: str | None = None,
        goal: str | None = None,
        defer_server_start: bool = False,
        server_kwargs: dict[str, Any] | None = None,
        mcp_server_info: list | None = None,
    ) -> None:
        super().__init__()
        self._assistant_id = assistant_id
        self._client = client
        self._server = server
        if not model and not defer_server_start:
            try:
                from dcoder.model.factory import _get_default_model_spec
                model = _get_default_model_spec()
            except Exception:
                model = ""
                defer_server_start = True
        self._model = model or ""
        self._server_startup_deferred = defer_server_start
        from dcoder.config.settings import settings
        self._settings = settings
        self._reasoning_effort: str | None = getattr(settings, "reasoning_effort", None)

        # Sync model metadata to settings early so /config can display it
        # before the agent is created (apply_to_settings only runs on first turn)
        if model and not settings.model_name:
            if ":" in model:
                provider_part, model_part = model.split(":", 1)
                settings.model_provider = provider_part
                settings.model_name = model_part
            else:
                settings.model_name = model
        self._auto_approve = auto_approve
        self._resume_thread = resume_thread
        self._goal = goal
        self._agent_thread_id: str | None = None

        # ── State Flags ──────────────────────────────────
        self._agent_running = False
        self._shell_running = False
        self._connecting = server_kwargs is not None and client is None
        self._startup_sequence_running = False
        self._server_startup_error: Exception | None = None
        self._exit = False

        # ── Worker Handles ───────────────────────────────
        self._agent_worker: Any | None = None
        self._shell_worker: Any | None = None
        self._shell_process: asyncio.subprocess.Process | None = None

        # ── Queue ────────────────────────────────────────
        self._pending_messages: deque[QueuedMessage] = deque()
        self._queued_widgets: deque[QueuedUserMessage] = deque()
        self._processing_pending = False

        # ── Adapter & Widgets ────────────────────────────
        self._adapter: TextualAdapter | None = None
        self._chat_input: ChatInput | None = None
        # Autocomplete is now managed inline by ChatInput
        self._loading_widget: Any | None = None

        # ── Typing Detection ─────────────────────────────
        self._last_typed_at: float | None = None

        # Deferred server startup
        self._server_kwargs = server_kwargs
        self._server_proc: Any = None
        self._mcp_session_manager: Any | None = None
        self._mcp_server_info = mcp_server_info or []

        # Register themes
        self._init_themes()

        # Session-scoped permission grants (Phase 3)
        # Full permission store with allow/ask/deny rules, persisted to config.toml
        self._permission_store: PermissionStore = load_permission_store()

        # ── Command Router ────────────────────────────────
        from dcoder.commands import CommandRouter
        self._command_router = CommandRouter()
        self._command_router.auto_discover()

    def _init_themes(self) -> None:
        """Register DCoder brand and custom themes and apply initial preference."""
        try:
            register_app_themes(self)
            initial_theme = load_theme_preference()
            self.theme = initial_theme if initial_theme in get_registry() else "dcoder-dark"
        except Exception:
            logger.exception("Failed to register themes")
            self.theme = "dcoder-dark"

    def get_theme_variable_defaults(self) -> dict[str, str]:
        """Return custom CSS variable defaults for the current theme.

        Most styling uses Textual's built-in variables (``$primary``,
        ``$text-muted``, ``$error-muted``, etc.).  This override injects the
        app-specific variables (``$mode-bash``, ``$mode-command``,
        ``$mode-incognito``, ``$skill``, ``$skill-hover``, ``$tool``,
        ``$tool-hover``, and the DevOps-specific tokens) that have no Textual
        equivalent.

        Returns:
            Dict of CSS variable names to hex color values.
        """
        from dcoder.ui.theme import get_css_variable_defaults, get_theme_colors

        colors = get_theme_colors(self)
        return get_css_variable_defaults(colors=colors)


    # ── Layout ───────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield MessageList(id="messages")
        with Container(id="bottom-container"):
            yield ChatInput(id="input-area")
        yield StatusBar(id="status-bar")

    # ── Lifecycle ────────────────────────────────────────

    async def on_mount(self) -> None:
        """Initialize TUI and optionally start server in the background."""
        logger.debug("TUI: on_mount start")

        messages_widget = self.query_one("#messages", MessageList)
        status_bar = self.query_one("#status-bar", StatusBar)
        eff = getattr(self, "_reasoning_effort", None) or (getattr(getattr(self, "settings", None), "reasoning_effort", None))
        status_bar.set_model(self._model or "", effort=eff or "")
        status_bar.set_approval_mode("manual" if not self._auto_approve else "auto")

        # Create adapter early with client=None (will be bound on ServerReady)
        self._adapter = TextualAdapter(
            client=self._client,
            assistant_id=self._assistant_id,
            messages_widget=messages_widget,
            status_bar=status_bar,
            auto_approve=self._auto_approve,
            set_spinner=self._set_spinner,
            app=self,
        )

        self._chat_input = self.query_one("#input-area", ChatInput)
        self._chat_input.focus()

        messages_widget.mount(WelcomeBanner())

        # Always refocus input after mounting widgets that may steal focus
        self._chat_input.focus()

        if self._server_startup_deferred:
            status_bar.set_status("Authentication required")
            await self._mount_message(
                SystemMessage(
                    "🔒 **No API credentials configured.**\n\n"
                    "Please set your API key in the environment or run `/login` to configure your credentials."
                )
            )
        elif self._connecting:
            # Deferred server startup — TUI is visible immediately
            status_bar.set_status("Connecting...")
            self._startup_sequence_running = True
            await self._mount_message(
                SystemMessage(
                    "⏳ **Starting agent server...** The TUI is ready — "
                    "the server will connect in the background."
                )
            )
            self.run_worker(self._start_server_background(), group="server-startup")
        elif self._client:
            # Eagerly-provided client (e.g. tests or pre-started server)
            await self._finalize_connection(self._client)
        else:
            # No server at all — offline/widget-only mode
            self._agent_thread_id = "local_session"
            await self._mount_message(
                SystemMessage(
                    "🚀 **DCoder TUI Ready** (offline) — "
                    "Type `/help` for slash commands."
                )
            )

        if self._goal:
            self.call_later(self._send_goal)

    async def _set_spinner(self, status: str | None) -> None:
        """Show, update, or hide the loading spinner in the message list matching reference dcode."""
        from dcoder.ui.loading import LoadingWidget

        if status is None:
            if self._loading_widget is not None:
                try:
                    await self._loading_widget.remove()
                except Exception:
                    pass
                self._loading_widget = None
            return

        try:
            messages = self.query_one("#messages", MessageList)
        except Exception:
            return

        if self._loading_widget is None or not getattr(self._loading_widget, "is_attached", False):
            self._loading_widget = LoadingWidget(status)
            messages.mount(self._loading_widget)
        else:
            if hasattr(self._loading_widget, "resume"):
                self._loading_widget.resume()
            if hasattr(self._loading_widget, "set_status"):
                self._loading_widget.set_status(status)

    # ── Widget Mount Helper ──────────────────────────────

    async def _mount_message(self, widget: Any) -> None:
        """Mount a message widget in the message list.

        Centralizes mount logic so scroll anchoring and error handling
        are in one place.

        Args:
            widget: Message widget to mount.
        """
        try:
            messages = self.query_one("#messages", MessageList)
            await messages.mount(widget)
            messages.scroll_end(animate=False)
        except Exception:
            logger.debug("Could not mount message (app closing?)", exc_info=True)

    # ── Deferred Server Startup ──────────────────────────

    async def maybe_start_deferred_server(self) -> bool:
        """Start the background server if startup was deferred due to missing credentials."""
        if not self._server_startup_deferred:
            return False

        from dcoder.exceptions import ModelConfigError, NoCredentialsConfiguredError
        from dcoder.model.factory import _get_default_model_spec

        try:
            model_spec = _get_default_model_spec()
        except (NoCredentialsConfiguredError, ModelConfigError):
            return False

        self._server_startup_deferred = False
        self._model = model_spec
        self._connecting = True
        self._server_kwargs = {
            "assistant_id": self._assistant_id,
            "model_name": model_spec,
            "auto_approve": self._auto_approve,
        }

        try:
            status_bar = self.query_one(StatusBar)
            status_bar.set_status("Connecting...")
        except Exception:
            pass

        await self._mount_message(
            SystemMessage(
                f"⏳ **Credentials configured!** Starting agent server for model `{model_spec}`..."
            )
        )
        self.run_worker(self._start_server_background(), group="server-startup")
        return True

    async def _start_server_background(self) -> None:
        """Background worker: start the LangGraph server subprocess.

        On success → posts ``ServerReady(client, server_proc)``
        On failure → posts ``ServerStartFailed(error)``
        """
        from dcoder.cli.server_manager import start_server_and_get_agent

        try:
            kwargs = dict(self._server_kwargs or {})
            assistant_id = str(kwargs.pop("assistant_id", self._assistant_id))
            client, server_proc = await start_server_and_get_agent(
                assistant_id=assistant_id,
                **kwargs,
            )
            self._server_proc = server_proc
            self.post_message(self.ServerReady(client=client, server_proc=server_proc))
        except Exception as exc:
            logger.exception("Server startup failed: %s", exc)
            self.post_message(self.ServerStartFailed(error=exc))

    @on(ServerReady)
    async def _on_server_ready(self, event: ServerReady) -> None:
        """Handle successful background server startup."""
        self._client = event.client
        self._server_proc = event.server_proc

        # Bind the now-live client to the adapter
        if self._adapter:
            self._adapter.set_client(event.client)

        await self._finalize_connection(event.client)
        self._connecting = False
        self._startup_sequence_running = False

        await self._mount_message(
            SystemMessage(
                "🚀 **Agent server connected!** "
                "Type `/help` for slash commands or enter a prompt."
            )
        )
        logger.debug("TUI: server ready, client bound to adapter")

        # Restore focus to input after async server startup
        if self._chat_input:
            self._chat_input.focus()

        # Drain any messages queued during connection
        await self._process_next_from_queue()

    @on(ServerStartFailed)
    async def _on_server_start_failed(self, event: ServerStartFailed) -> None:
        """Handle server startup failure — show error and allow recovery."""
        self._connecting = False
        self._startup_sequence_running = False
        self._server_startup_error = event.error

        # Clear any queued messages
        self._pending_messages.clear()
        while self._queued_widgets:
            widget = self._queued_widgets.popleft()
            try:
                await widget.remove()
            except Exception:
                pass

        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.set_status("Server Error")
        except NoMatches:
            pass

        await self._mount_message(
            ErrorMessage(
                f"Server startup failed: {event.error}\n\n"
                "Check your API key (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`) "
                "and relaunch, or use `/model` to reconfigure."
            )
        )
        logger.error("Server startup failed: %s", event.error)

        # Keep input focusable for slash commands even after failure
        if self._chat_input:
            self._chat_input.focus()

    async def _finalize_connection(self, client: Any) -> None:
        """Create thread and mark the app as ready for agent turns."""
        if self._resume_thread:
            self._agent_thread_id = self._resume_thread
        else:
            import uuid
            self._agent_thread_id = str(uuid.uuid4())

        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.set_status("Ready")
        except NoMatches:
            pass
        logger.debug("TUI: connection finalized, thread_id=%s", self._agent_thread_id)

    async def _send_goal(self) -> None:
        if self._goal:
            await self._submit_input(self._goal, "normal")

    # ── Autocomplete Event Handlers ──────────────────────

    @on(ChatInput.SlashCommandStarted)
    def _on_slash_started(self, event: ChatInput.SlashCommandStarted) -> None:
        """Autocomplete is now managed inline by ChatInput — no app-level action needed."""

    @on(ChatInput.SlashCommandEnded)
    def _on_slash_ended(self, event: ChatInput.SlashCommandEnded) -> None:
        """Autocomplete is now managed inline by ChatInput — no app-level action needed."""

    @on(AutocompletePopup.CommandSelected)
    def _on_command_selected(self, event: AutocompletePopup.CommandSelected) -> None:
        """Insert selected command into chat input and submit if zero-arg or submitted via Enter."""
        if not self._chat_input:
            return

        # Hide the inline popup
        self._chat_input._autocomplete.hide_popup()

        cmd = get_command(event.command_name)
        has_args = bool(cmd and cmd.argument_hint)

        if event.by_enter or not has_args:
            # Execute command immediately (e.g. /theme opens modal popup instantly on single Enter)
            self._chat_input.text = event.command_name
            self._chat_input._submit_value()
        else:
            # Insert command prefix with space for argument input (e.g. /effort [level])
            self._chat_input.text = f"{event.command_name} "
            self._chat_input.focus_input()


    @on(ChatInput.Typing)
    def _on_typing(self, event: ChatInput.Typing) -> None:
        """Record the most recent keystroke time for typing-aware approval deferral."""
        self._last_typed_at = _monotonic()

    def _is_user_typing(self) -> bool:
        """Return whether the user typed recently (within idle threshold)."""
        if self._last_typed_at is None:
            return False
        return (_monotonic() - self._last_typed_at) < _TYPING_IDLE_THRESHOLD_SECONDS

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Copy selection to clipboard after click-chain selection updates."""
        from dcoder.ui.clipboard import copy_selection_to_clipboard
        self.call_after_refresh(copy_selection_to_clipboard, self)

    # ── Input Submission Pipeline (dcode pattern) ────────

    @on(ChatInput.Submitted)
    async def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        """Handle submitted input from ChatInput widget.

        This is the SINGLE entry point for user input.  It feeds into
        ``_submit_input`` which handles queueing, bypass tiers, and
        routing — never spawns a worker directly.
        """
        value = event.value
        mode: InputMode = event.mode  # type: ignore[assignment]
        await self._submit_input(value, mode)

    def _can_bypass_queue(self, value: str) -> bool:
        """Check if a command can bypass the busy-state queue.

        Args:
            value: Lowered, stripped command text.

        Returns:
            ``True`` if the command should bypass the queue.
        """
        cmd = value.split(maxsplit=1)[0] if value else ""

        if cmd in IMMEDIATE_UI_CMDS:
            # Only bare form (no args) bypasses — e.g. /model opens selector,
            # /model <name> does a direct switch that shouldn't race with agent.
            return value == cmd

        return False

    async def _submit_input(
        self,
        value: str,
        mode: InputMode,
        *,
        force_bypass: bool = False,
    ) -> None:
        """Submit input, fast-pathing always-immediate commands.

        For commands in ``ALWAYS_IMMEDIATE`` (or whenever ``force_bypass``
        is set), the value is processed directly.  Otherwise the standard
        queue and per-tier bypass policy applies.

        Args:
            value: Raw text submitted by the user.
            mode: Input routing mode.
            force_bypass: Skip queueing and process immediately.
        """
        # Always-immediate commands (e.g. /quit, /force-clear)
        if force_bypass or (
            mode == "command" and value.lower().strip().split(maxsplit=1)[0] in ALWAYS_IMMEDIATE
        ):
            await self._process_message(value, mode)
            return

        # If the app is busy, enqueue instead of processing
        if (
            self._agent_running
            or self._shell_running
            or self._connecting
            or self._startup_sequence_running
            or self._server_startup_error is not None
        ):
            # Check if this command can bypass the queue
            if mode == "command" and self._can_bypass_queue(value.lower().strip()):
                await self._process_message(value, mode)
                return

            # Enqueue
            self._pending_messages.append(QueuedMessage(text=value, mode=mode))
            queued_widget = QueuedUserMessage(value)
            self._queued_widgets.append(queued_widget)
            await self._mount_message(queued_widget)
            self._sync_status_queued()

            if self._connecting:
                self.notify(
                    "Server is connecting. Your message is queued.",
                    severity="information",
                    timeout=3,
                )
            return

        await self._process_message(value, mode)

    async def _process_message(self, value: str, mode: InputMode) -> None:
        """Route a message to the appropriate handler based on mode.

        Args:
            value: The message text to process.
            mode: The input mode that determines message routing.
        """
        if mode == "shell_incognito":
            cmd = value.removeprefix("!!").removeprefix("!")
            await self._handle_shell_command(cmd, incognito=True)
        elif mode == "shell":
            cmd = value.removeprefix("!")
            await self._handle_shell_command(cmd)
        elif mode == "command":
            await self._handle_command(value)
        elif mode == "normal":
            await self._handle_user_message(value)
        else:
            logger.error(
                "Unrecognized input mode %r; refusing to forward to agent",
                mode,
            )
            await self._mount_message(
                ErrorMessage(
                    f"Internal error: unknown input mode {mode!r}. "
                    "Message was not sent."
                )
            )

    def _sync_status_queued(self) -> None:
        """Update status bar with queue depth."""
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            count = len(self._pending_messages)
            if count > 0:
                status_bar.set_status(f"{count} queued")
            elif not (self._agent_running or self._shell_running):
                status_bar.set_status("Ready")
        except NoMatches:
            pass

    # ── Agent Turn Lifecycle ─────────────────────────────

    async def _handle_user_message(self, message: str) -> None:
        """Handle a user message to send to the agent.

        Mounts the user message widget and dispatches to the agent
        via a single worker.

        Args:
            message: The user's message.
        """
        await self._mount_message(UserMessage(message))
        await self._send_to_agent(message)

    async def _send_to_agent(self, message: str) -> None:
        """Send a message to the agent and start execution.

        This is the low-level send path.  The caller mounts the visual
        representation first (``UserMessage``, ``SkillMessage``, etc.).

        Args:
            message: The prompt to send to the agent.
        """
        # Anchor scroll so streaming response stays visible
        with suppress(NoMatches):
            self.query_one("#messages", MessageList).scroll_end(animate=False)

        # Check if agent is available
        if self._adapter and self._adapter.connected and self._agent_thread_id:
            self._agent_running = True

            if self._chat_input:
                # Visual hint that input is busy
                pass

            # Spawn a single worker for the agent task
            self._agent_worker = self.run_worker(
                self._run_agent_task(message),
                exclusive=False,
            )
        elif self._server_startup_error is not None:
            await self._mount_message(
                ErrorMessage(
                    "Cannot send prompt: Agent server failed to start. "
                    "Check your API key and relaunch, or use `/model` to reconfigure."
                )
            )
        elif not self._adapter or not self._adapter.connected:
            await self._mount_message(
                ErrorMessage(
                    "Agent not connected. Server may still be starting — "
                    "try again in a moment."
                )
            )

    async def _run_agent_task(self, message: str) -> None:
        """Run the agent task in a background worker.

        This runs in a Textual worker so the main event loop stays responsive.
        ``_cleanup_agent_task`` always runs in the ``finally`` block.

        Args:
            message: The prompt to send to the agent.
        """
        if self._adapter is None:
            return

        try:
            context = {"model": self._model} if self._model else None
            await self._adapter.stream_turn(
                prompt=message,
                thread_id=self._agent_thread_id or "local_session",
                context=context,
            )
        except asyncio.CancelledError:
            logger.debug("Agent task cancelled")
        except Exception as e:
            logger.exception("Agent execution failed: %s", e)
            await self._mount_message(
                ErrorMessage(_format_error_detail(e))
            )

        finally:
            await self._cleanup_agent_task()

    async def _cleanup_agent_task(self) -> None:
        """Clean up after agent task completes or is cancelled.

        Always runs in the ``finally`` block of ``_run_agent_task``.
        Guaranteed to drain the queue.
        """
        self._agent_running = False
        self._agent_worker = None

        if self._chat_input:
            self._chat_input.focus()

        # Process next message from queue
        await self._process_next_from_queue()

    # ── Shell Command Execution ──────────────────────────

    async def _handle_shell_command(
        self,
        command: str,
        *,
        incognito: bool = False,
    ) -> None:
        """Handle a shell command (``!`` prefix).

        Mounts the user message and spawns a worker so the event loop
        stays free for key events (Esc/Ctrl+C).

        Args:
            command: The shell command to execute.
            incognito: Whether command/output should remain local-only.
        """
        if not incognito:
            await self._mount_message(UserMessage(f"!{command}"))
        self._shell_running = True

        self._shell_worker = self.run_worker(
            self._run_shell_task(command, incognito=incognito),
            exclusive=False,
        )

    async def _run_shell_task(
        self,
        command: str,
        *,
        incognito: bool = False,
    ) -> None:
        """Run a shell command in a background worker.

        Args:
            command: The shell command to execute.
            incognito: Whether command/output should remain local-only.
        """
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=(sys.platform != "win32"),
            )
            self._shell_process = proc

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=_SHELL_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                await self._kill_shell_process()
                await self._mount_message(
                    ErrorMessage(f"Command timed out ({_SHELL_TIMEOUT_SECONDS}s limit)")
                )
                return
            except asyncio.CancelledError:
                await self._kill_shell_process()
                raise

            output = (stdout_bytes or b"").decode(errors="replace").strip()
            stderr_text = (stderr_bytes or b"").decode(errors="replace").strip()
            if stderr_text:
                output += f"\n[stderr]\n{stderr_text}"

            if output:
                messages = self.query_one("#messages", MessageList)
                messages.start_assistant_message()
                messages.append_assistant_token(f"```text\n{output}\n```")
                messages.finish_assistant_message()
            else:
                await self._mount_message(
                    SystemMessage("Command completed (no output)")
                )

            if proc.returncode and proc.returncode != 0:
                await self._mount_message(
                    ErrorMessage(f"Exit code: {proc.returncode}")
                )

        except asyncio.CancelledError:
            logger.debug("Shell task cancelled")
        except Exception as e:
            logger.exception("Shell command failed: %s", e)
            await self._mount_message(ErrorMessage(f"Shell error: {e!r}"))
        finally:
            self._shell_running = False
            self._shell_process = None
            self._shell_worker = None
            # Drain queue after shell completes
            await self._process_next_from_queue()

    async def _kill_shell_process(self) -> None:
        """Terminate the active shell process."""
        proc = self._shell_process
        if proc is None:
            return
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=5)
        except (TimeoutError, ProcessLookupError):
            with suppress(ProcessLookupError):
                proc.kill()

    # ── Queue Processing ─────────────────────────────────

    async def _process_next_from_queue(self) -> None:
        """Process the next message from the queue if any exist.

        Uses ``_processing_pending`` to prevent re-entrant execution.
        """
        if self._processing_pending or not self._pending_messages or self._exit:
            return

        self._processing_pending = True
        msg: QueuedMessage | None = None
        try:
            msg = self._pending_messages.popleft()
            self._sync_status_queued()

            # Remove the ephemeral queued-message widget
            if self._queued_widgets:
                widget = self._queued_widgets.popleft()
                try:
                    await widget.remove()
                except Exception:
                    pass

            await self._process_message(msg.text, msg.mode)
        except Exception:
            logger.exception("Failed to process queued message")
            err_snippet = msg.text[:60] if msg else "unknown message"
            await self._mount_message(
                ErrorMessage(f"Failed to process queued message: {err_snippet}")
            )
        finally:
            self._processing_pending = False


        # Command-mode messages complete synchronously; continue draining
        busy = self._agent_running or self._shell_running
        if not busy and self._pending_messages:
            await self._process_next_from_queue()

    # ── Slash Command Registry Dispatch ──────────────────

    async def _handle_command(self, text: str) -> None:
        """Dispatch slash command via command_registry.

        Commands execute synchronously (no worker).  Only DevOps commands
        that need agent interaction re-enter via ``_send_to_agent``.

        Args:
            text: Full command text including ``/`` prefix.
        """
        parts = text.split(maxsplit=1)
        cmd_name = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        # ── Router Dispatch Check ────────────────────────
        handler = self._command_router.get_handler(cmd_name)
        if handler is not None:
            if self._agent_running and handler.bypass_tier == BypassTier.QUEUED:
                self._pending_messages.append(QueuedMessage(text=text, mode="command"))
                await self._mount_message(
                    SystemMessage(f"⏳ Command `{cmd_name}` queued...")
                )
                return

            if cmd_name not in {"/exit", "/quit", "/q", "/clear", "/force-clear"}:
                await self._mount_message(UserMessage(text))

            from dcoder.commands import CommandContext
            from dcoder.config.settings import settings as global_settings
            ctx = CommandContext(
                app=self,
                session=getattr(self, "_session_state", None),
                agent=getattr(self, "_agent", None),
                settings=getattr(self, "_settings", None) or global_settings,
                raw_command=text,
                args=arg,
                thread_id=self._agent_thread_id,
                model_spec=self._model,
            )
            res = await self._command_router.dispatch(text, ctx)
            if res.mount_as_app_message and res.message:
                await self._mount_message(SystemMessage(res.message))
            if res.notify:
                self.notify(res.notify, severity=res.notify_severity)
            if res.push_screen:
                self.push_screen(res.push_screen)
            return

        command = get_command(cmd_name)

        if not command:
            await self._mount_message(
                SystemMessage(f"Unknown command: `{cmd_name}`. Try `/help`.")
            )
            return

        # Check queueing for QUEUED tier when busy
        if self._agent_running and command.bypass_tier == BypassTier.QUEUED:
            self._pending_messages.append(QueuedMessage(text=text, mode="command"))
            await self._mount_message(
                SystemMessage(f"⏳ Command `{cmd_name}` queued...")
            )
            return

        if cmd_name not in {"/exit", "/quit", "/q", "/clear", "/force-clear"}:
            await self._mount_message(UserMessage(text))

        # ── Dispatch (Fallback for unmigrated inline commands) ──────

        if cmd_name == "/theme":
            if arg:
                await self._switch_theme(arg)
            else:
                await self._show_theme_selector()

        elif cmd_name == "/agents":
            if arg:
                # Direct switch: /agents <name>
                self._switch_agent(arg)
            else:
                # Open interactive picker
                await self._show_agent_selector()

        elif cmd_name == "/goal":
            if arg:
                self._goal = arg
                await self._mount_message(
                    SystemMessage(f"Persistent Goal Set: `{arg}`")
                )
            else:
                await self._mount_message(
                    SystemMessage(f"Current Goal: `{self._goal or 'None'}`")
                )

        # ── DevOps Commands Placeholder ──────────────────
        elif cmd_name == "/plan":
            await self._handle_user_message(f"Run terraform plan on {arg or '.'}")

        elif cmd_name == "/apply":
            await self._handle_user_message(f"Run terraform apply on {arg or '.'}")

        elif cmd_name == "/kctx":
            await self._handle_user_message(f"Show kubernetes context {arg}")

        elif cmd_name == "/pods":
            await self._handle_user_message(
                f"Get kubernetes pods in namespace {arg or 'default'}"
            )

        elif cmd_name == "/deploy":
            await self._handle_user_message(
                f"Trigger deployment for {arg or 'current project'}"
            )

        elif cmd_name == "/infra":
            panel = self.query(InfraStatePanel)
            if panel:
                panel.first().remove()
            else:
                self.mount(InfraStatePanel())

    # ── Phase 2 Helper Methods ────────────────────────────

    def prepare_exit(self) -> None:
        """Clear message queues and cancel active adapter workers prior to termination."""
        self._pending_messages.clear()
        self._queued_widgets.clear()
        if self._adapter:
            self._adapter.cancel()

    def get_latest_assistant_message(self) -> str | None:
        """Retrieve latest assistant message content for clipboard copy."""
        try:
            from dcoder.ui.messages import AssistantMessage
            msgs = list(self.query(AssistantMessage))
            for latest in reversed(msgs):
                msg_text = getattr(latest, "content_text", None) or "".join(getattr(latest, "_fragments", []))
                if not msg_text or not msg_text.strip():
                    continue
                if getattr(latest, "is_streaming", False):
                    continue
                return msg_text
        except Exception:
            pass
        return None

    async def _load_thread_history(self, thread_id: str) -> None:
        """Fetch and mount stored message history for a thread from SessionManager."""
        from pathlib import Path
        from dcoder.state.session import SessionManager
        from dcoder.ui.messages import UserMessage, AssistantMessage, ToolCallMessage

        sm = None
        session_state = getattr(self, "_session_state", None)
        if session_state and hasattr(session_state, "session_manager"):
            sm = session_state.session_manager
        else:
            db_path = Path.home() / ".dcoder" / ".state" / "sessions.db"
            if db_path.exists():
                sm = SessionManager(db_path)

        if sm is None:
            return

        messages_to_mount = await sm.get_thread_messages(thread_id)


        for msg in messages_to_mount:
            content = getattr(msg, "content", None)
            if content is None:
                continue

            if isinstance(content, list):
                txt_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        txt_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        txt_parts.append(block)
                content = "".join(txt_parts).strip()

            if not content:
                continue

            msg_type = type(msg).__name__
            if msg_type == "HumanMessage" or getattr(msg, "type", "") == "human":
                if not str(content).startswith("System Prompt"):
                    await self._mount_message(UserMessage(str(content)))
            elif msg_type == "AIMessage" or getattr(msg, "type", "") == "ai":
                await self._mount_message(AssistantMessage(str(content)))
            elif msg_type == "ToolMessage" or getattr(msg, "type", "") == "tool":
                call_id = getattr(msg, "tool_call_id", "call_1") or "call_1"
                tool_widget = ToolCallMessage(name="Tool Result", call_id=call_id, args={})
                tool_widget.set_result(str(content), success=True)
                await self._mount_message(tool_widget)

    async def resume_thread(self, thread_id: str, *, is_new: bool = False) -> None:
        """Resume conversation from specified checkpoint thread ID and restore history."""
        self._agent_thread_id = thread_id
        session_state = getattr(self, "_session_state", None)
        if session_state:
            session_state.thread_id = thread_id
        self._pending_messages.clear()
        self._queued_widgets.clear()
        try:
            from dcoder.ui.messages import MessageList
            messages = self.query_one("#messages", MessageList)
            messages.clear()
        except NoMatches:
            pass

        label = "✨ Created new thread" if is_new else "🔄 Resumed thread"
        await self._mount_message(
            SystemMessage(f"{label}: `{thread_id}`")
        )
        if not is_new:
            await self._load_thread_history(thread_id)


    async def invoke_compact_conversation(self, thread_id: str | None = None, force: bool = True) -> None:
        """Trigger server-side conversation summarization/compaction."""
        from dcoder.commands.core.compact import CompactHandler
        from dcoder.commands._base import CommandContext
        handler = CompactHandler()
        ctx = CommandContext(
            raw_command="/compact",
            args="",
            app=self,
            agent=getattr(self, "_agent_graph", None),
        )
        await handler.execute(ctx)

    def toggle_timestamps(self, visible: bool | None = None) -> bool:
        """Toggle message timestamps visibility across chat messages."""
        if visible is not None:
            self._message_timestamps_visible = visible
        else:
            self._message_timestamps_visible = not getattr(self, "_message_timestamps_visible", False)
        try:
            from dcoder.ui.messages import MessageList
            messages = self.query_one("#messages", MessageList)
            messages.set_timestamps_visible(self._message_timestamps_visible)
        except Exception:
            pass
        return self._message_timestamps_visible

    def get_context_tokens(self) -> int:
        """Get total input + output tokens consumed in current session."""
        if self._adapter and hasattr(self._adapter, "stats") and self._adapter.stats:
            return getattr(self._adapter.stats, "input_tokens", 0) + getattr(self._adapter.stats, "output_tokens", 0)
        return 0

    async def _get_conversation_token_count(self) -> int | None:
        """Get approximate token count of conversation message history matching reference dcode."""
        try:
            msgs = self.get_thread_messages()
            if not msgs:
                return None
            from langchain_core.messages.utils import count_tokens_approximately
            return count_tokens_approximately(msgs)
        except Exception:
            return None

    async def get_conversation_token_count(self) -> int | None:
        """Get approximate token count of conversation message history."""
        return await self._get_conversation_token_count()

    def get_thread_messages(self) -> list:
        """Fetch current thread messages from UI widgets or adapter."""
        msgs = []
        try:
            from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
            from dcoder.ui.messages import UserMessage, AssistantMessage, ToolCallMessage, MessageList
            container = self.query_one("#messages", MessageList)
            for child in container.children:
                if isinstance(child, UserMessage):
                    txt = getattr(child, "_raw_content", "") or ""
                    if txt:
                        msgs.append(HumanMessage(content=txt))
                elif isinstance(child, AssistantMessage):
                    txt = getattr(child, "content_text", None) or "".join(getattr(child, "_fragments", []))
                    if txt:
                        msgs.append(AIMessage(content=txt))
                elif isinstance(child, ToolCallMessage):
                    res = getattr(child, "_result", "") or ""
                    call_id = getattr(child, "_call_id", "") or "call_1"
                    if res:
                        msgs.append(ToolMessage(content=str(res), tool_call_id=call_id))
        except Exception:
            pass
        return msgs

    def get_active_tools(self) -> list[dict[str, str]]:
        """Get list of active core tools with names and descriptions."""
        return [
            {"name": "read_file", "description": "Read file contents with line range filtering."},
            {"name": "write_file", "description": "Create new files or overwrite existing files."},
            {"name": "edit_file", "description": "Perform precise contiguous block edits on a file."},
            {"name": "run_command", "description": "Execute terminal shell commands on system."},
            {"name": "grep_search", "description": "Fast regex and exact string pattern searching."},
            {"name": "list_dir", "description": "List contents and metadata of workspace directories."},
            {"name": "view_file", "description": "View text and binary files (images, pdfs)."},
        ]

    def get_mcp_servers(self) -> list:
        """Return MCP server metadata for /mcp, /skills, and /doctor commands."""
        return getattr(self, "_mcp_server_info", [])

    def get_discovered_skills(self) -> list[dict[str, Any]]:
        """Get list of discovered skills (project, user, plugin, built-in)."""
        from pathlib import Path
        from dcoder.config.settings import settings
        from dcoder.skills.loader import list_skills

        built_in_dir = Path(__file__).parent.parent / "built_in_skills"
        user_skills_dir = settings.get_user_skills_dir("dcoder")
        project_skills_dir = settings.get_project_skills_dir()

        skills = list_skills(
            built_in_skills_dir=built_in_dir,
            user_skills_dir=user_skills_dir,
            project_skills_dir=project_skills_dir,
            include_plugins=True,
        )
        return [dict(s) for s in skills]



    async def switch_model(self, model_name: str, extra_kwargs: dict | None = None) -> None:
        """Switch active LLM model."""
        self.run_worker(
            self._switch_model(model_name),
            exclusive=False,
            group="model-switch",
        )

    async def set_default_model(self, model_name: str) -> None:
        """Set default model in settings."""
        self._model = model_name

    async def clear_default_model(self) -> None:
        """Clear default model setting."""
        pass

    def save_previous_model(self, model: str | None, effort: str | None) -> None:
        """Save previous model and reasoning effort before fast mode toggle."""
        self._prev_model = model
        self._prev_effort = effort

    def get_previous_model(self) -> str | None:
        """Get previously saved model name."""
        return getattr(self, "_prev_model", None)

    def get_previous_effort(self) -> str | None:
        """Get previously saved reasoning effort."""
        return getattr(self, "_prev_effort", None)

    def _update_auto_mode_status_bar(self, mode: str) -> None:
        """Update TUI status bar indicator badge for auto-mode."""
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            badge = "🟢 AUTO" if mode == "auto" else "🔴 MANUAL"
            status_bar.set_status(f"Ready ({badge})")
        except NoMatches:
            pass

    def _force_interrupt_active_work(self) -> None:
        """Force-interrupt any active agent or shell work."""
        if self._adapter:
            self._adapter.cancel()
        if self._agent_worker:
            self._agent_worker.cancel()
        if self._shell_worker:
            self._shell_worker.cancel()
        self._agent_running = False
        self._shell_running = False

    # ── TextualAdapter Event Handlers ────────────────────

    @on(TextualAdapter.TokenStreamed)
    def _on_adapter_token(self, event: TextualAdapter.TokenStreamed) -> None:
        pass

    @on(TextualAdapter.ToolCallStarted)
    def _on_tool_started(self, event: TextualAdapter.ToolCallStarted) -> None:
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.set_status(f"Running tool: {event.name}")
        except NoMatches:
            pass

    @on(TextualAdapter.ToolCallCompleted)
    def _on_tool_completed(self, event: TextualAdapter.ToolCallCompleted) -> None:
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.set_status("Thinking...")
        except NoMatches:
            pass

    @on(TextualAdapter.InterruptRaised)
    def _on_interrupt_raised(self, event: TextualAdapter.InterruptRaised) -> None:
        if self._auto_approve and self._adapter:
            self._adapter.submit_approval(event.call_id, True)
            return

        risk = assess_tool_risk(event.tool_name, event.args)

        if risk == "high":
            modal = ApprovalModalScreen(event.tool_name, event.call_id, event.args)

            def _on_modal_dismiss(decision: ApprovalDecided | None) -> None:
                if decision and self._adapter:
                    self._adapter.submit_approval(event.call_id, decision.approved)

            self.push_screen(modal, callback=_on_modal_dismiss)
        else:
            try:
                messages = self.query_one("#messages", MessageList)
                messages.mount(
                    ApprovalMenu(event.tool_name, event.call_id, event.args, risk=risk)
                )
            except NoMatches:
                pass

    @on(ApprovalDecided)
    def _on_approval_decided(self, event: ApprovalDecided) -> None:
        if self._adapter:
            self._adapter.submit_approval(event.call_id, event.approved)
        # Track denied actions in permission store for "Recently Denied" tab
        if not event.approved and hasattr(self, "_permission_store"):
            self._permission_store.track_denied(
                tool_name=event.tool_name,
                call_id=event.call_id,
                comment=event.comment,
            )
        # Refocus chat input after approval
        if self._chat_input:
            self.call_after_refresh(self._chat_input.focus)

    @on(TextualAdapter.SubagentSpawned)
    def _on_subagent_spawned(self, event: TextualAdapter.SubagentSpawned) -> None:
        try:
            messages = self.query_one("#messages", MessageList)
            panels = list(messages.query(SubagentPanel))
            if not panels:
                panel = SubagentPanel()
                messages.mount(panel)
            else:
                panel = panels[0]
            panel.spawn_subagent(event.agent_name, event.task)
        except NoMatches:
            pass

    @on(TextualAdapter.SubagentUpdate)
    def _on_subagent_update(self, event: TextualAdapter.SubagentUpdate) -> None:
        try:
            messages = self.query_one("#messages", MessageList)
            panels = list(messages.query(SubagentPanel))
            if panels:
                panels[0].append_token(event.agent_name, event.token)
        except NoMatches:
            pass

    @on(TextualAdapter.StreamFinished)
    async def _on_stream_finished(self, event: TextualAdapter.StreamFinished) -> None:
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.update_stats(event.stats)
        except NoMatches:
            pass
        # Note: queue draining is handled by _cleanup_agent_task, not here

    @on(TextualAdapter.StreamError)
    async def _on_stream_error(self, event: TextualAdapter.StreamError) -> None:
        show_toast(self, event.error, title="Stream Error", severity="error")
        # Note: queue draining is handled by _cleanup_agent_task, not here

    # ── Global Actions ───────────────────────────────────

    def action_interrupt(self) -> None:
        """Interrupt active agent or shell work."""
        if self._agent_running and self._adapter:
            self._adapter.cancel()
            try:
                self.query_one("#status-bar", StatusBar).set_status("Interrupted")
            except NoMatches:
                pass
        if self._shell_running:
            if self._shell_worker:
                self._shell_worker.cancel()

    def action_clear_chat(self) -> None:
        """Clear chat and start fresh (Ctrl+L)."""
        self._pending_messages.clear()
        self._queued_widgets.clear()
        try:
            messages = self.query_one("#messages", MessageList)
            messages.clear()
        except NoMatches:
            pass

    def action_toggle_auto_approve(self) -> None:
        """Toggle auto-approve mode (Shift+Tab) - Disabled."""
        self._auto_approve = False
        self._approval_mode = "suggest"
        self.notify("Auto-mode is currently disabled.", severity="warning", timeout=3)
        if self._adapter:
            self._adapter._auto_approve = False

    # ── Theme Selector Integration ────────────────────────

    async def _show_theme_selector(self) -> None:
        """Show interactive theme selector modal screen."""
        def handle_result(result: str | None) -> None:
            if result is not None and result in get_registry():
                self.theme = result
                save_theme_preference(result)
                show_toast(self, f"Switched theme to `{result}`", severity="information")
            if self._chat_input:
                self._chat_input.focus_input()


        screen = ThemeSelectorScreen(current_theme=self.theme)
        self.push_screen(screen, handle_result)

    async def _switch_theme(self, name: str) -> None:
        """Switch theme directly by name or alias."""
        registry = get_registry()
        target = name.strip()

        matched = None
        if target in registry:
            matched = target
        else:
            for key, entry in registry.items():
                if key.lower() == target.lower() or entry.label.lower() == target.lower():
                    matched = key
                    break

        if matched:
            self.theme = matched
            save_theme_preference(matched)
            await self._mount_message(
                SystemMessage(f"Switched to `{matched}` theme")
            )
        else:
            avail = ", ".join(f"`{k}`" for k in list(registry.keys())[:8])
            await self._mount_message(
                ErrorMessage(f"Unknown theme `{name}`. Available themes include: {avail}...")
            )

    # ── Thread Selector Integration ───────────────────────

    async def _show_thread_selector(self) -> None:
        """Open the interactive thread selector modal screen."""
        from dcoder.ui.thread_selector import ThreadSelectorScreen

        from pathlib import Path
        from dcoder.state.session import SessionManager

        threads = []
        sm = None
        session_state = getattr(self, "_session_state", None)
        if session_state and hasattr(session_state, "session_manager"):
            sm = session_state.session_manager
        else:
            db_path = Path.home() / ".dcoder" / ".state" / "sessions.db"
            if db_path.exists():
                sm = SessionManager(db_path)

        if sm is not None:
            try:
                raw_threads = await sm.list_threads(limit=50)
                threads = [
                    {
                        "thread_id": t.thread_id,
                        "created_at": t.created_at,
                        "updated_at": t.updated_at,
                        "message_count": t.message_count,
                        "initial_prompt": t.initial_prompt,
                    }
                    for t in raw_threads
                ]
            except Exception as exc:
                logger.debug("Failed fetching threads for selector: %s", exc)

        screen = ThreadSelectorScreen(
            threads=threads,
            current_thread_id=self._agent_thread_id,
        )

        def _on_thread_selected(selected_id: str | None) -> None:
            if selected_id == "__new__":
                import uuid
                new_id = str(uuid.uuid4())
                self.run_worker(self.resume_thread(new_id, is_new=True))
            elif selected_id:
                self.run_worker(self.resume_thread(selected_id, is_new=False))

        self.push_screen(screen, _on_thread_selected)

    async def get_recent_threads(self, limit: int = 20) -> list:
        """Get list of recent threads from session manager."""
        from pathlib import Path
        from dcoder.state.session import SessionManager

        sm = None
        session_state = getattr(self, "_session_state", None)
        if session_state and hasattr(session_state, "session_manager"):
            sm = session_state.session_manager
        else:
            db_path = Path.home() / ".dcoder" / ".state" / "sessions.db"
            if db_path.exists():
                sm = SessionManager(db_path)

        if sm is not None:
            try:
                return await sm.list_threads(limit=limit)
            except Exception:
                pass
        return []


    # ── Model Selector Integration ────────────────────────

    async def _show_model_selector(self) -> None:
        """Open the interactive model picker modal."""
        from dcoder.ui.model_selector import ModelSelectorScreen
        from dcoder.model.config import resolve_model_spec

        current_provider, current_model = None, None
        if self._model:
            try:
                current_provider, current_model = resolve_model_spec(self._model)
            except Exception:
                current_model = self._model
        
        settings_obj = getattr(self, "settings", None)
        current_effort = getattr(self, "_reasoning_effort", None) or (getattr(settings_obj, "reasoning_effort", None) if settings_obj else None)

        screen = ModelSelectorScreen(
            current_model=current_model,
            current_provider=current_provider,
            current_effort=current_effort,
        )

        def _on_model_selected(result: tuple[str, str, str | None] | tuple[str, str] | None) -> None:
            """Callback when the model selector is dismissed."""
            if result is None:
                return
            spec = result[0]
            effort = result[2] if len(result) > 2 else None
            extra = screen.pending_install_extra
            if extra:
                # Run in a worker so modal screens pushed during installation
                # remain interactive (call_later would block the message pump).
                self.run_worker(
                    self._install_extra_then_switch(extra, spec, effort=effort),
                    exclusive=False,
                    group="model-install-switch",
                )
            else:
                self.run_worker(
                    self._switch_model(spec, effort=effort),
                    exclusive=False,
                    group="model-switch",
                )

        self.push_screen(screen, _on_model_selected)

    async def _install_extra_then_switch(self, extra: str, spec: str, effort: str | None = None) -> None:
        """Install provider package extra, then check auth and switch model.

        Stops on install failure rather than falling through to auth/switch.
        After successful install, prompts for credentials if needed before
        performing the model switch.
        """
        await self._mount_message(
            SystemMessage(f"Installing '{extra}' integration package...")
        )

        pkg_name = f"langchain-{extra}"
        install_ok = False
        try:
            def _run_install():
                import shutil
                import subprocess
                import sys

                # Try pip first
                pip_res = subprocess.run(
                    [sys.executable, "-m", "pip", "install", pkg_name],
                    capture_output=True,
                    text=True,
                )
                if pip_res.returncode == 0:
                    return pip_res

                # pip failed (possibly not installed) — fall back to uv
                uv_bin = shutil.which("uv")
                if uv_bin:
                    return subprocess.run(
                        [uv_bin, "pip", "install", pkg_name],
                        capture_output=True,
                        text=True,
                    )

                # Neither pip nor uv succeeded
                return pip_res

            res = await asyncio.to_thread(_run_install)
            if res.returncode == 0:
                install_ok = True
                await self._mount_message(
                    SystemMessage(f"Successfully installed '{extra}' integration package.")
                )
            else:
                logger.warning("install %s failed with code %d: %s", pkg_name, res.returncode, res.stderr)
                await self._mount_message(
                    ErrorMessage(f"Failed to install '{extra}'. Check logs for details.")
                )
        except Exception as e:
            logger.warning("Failed to install package extra %s: %s", extra, e)
            await self._mount_message(
                ErrorMessage(f"Failed to install '{extra}': {e}")
            )

        if not install_ok:
            return

        # Package installed — now check if credentials are needed before switching.
        auth_ok = await self._prompt_model_auth_if_needed(spec)
        if not auth_ok:
            # User cancelled auth. Let them know the extra is installed so they
            # can switch later once a key is set.
            await self._mount_message(
                SystemMessage(
                    f"Installed '{extra}'. Switch to {spec} anytime with "
                    "`/model` — you'll be prompted for credentials."
                )
            )
            return

        await self._finalize_model_switch(spec, effort=effort)

    async def _prompt_model_auth_if_needed(self, spec: str) -> bool:
        """Prompt for missing credentials before switching to a model.

        Returns True when switching can continue, False when the user did not
        save required credentials.
        """
        from dcoder.model.config import (
            get_credential_env_var,
            get_provider_auth_status,
        )
        from dcoder.ui.auth import AuthPromptScreen, AuthResult

        provider = spec.split(":", 1)[0] if ":" in spec else "openai"
        status = get_provider_auth_status(provider)
        if status.as_legacy_bool():
            return True

        env_var = status.env_var or get_credential_env_var(provider) or f"{provider.upper()}_API_KEY"

        # Use an asyncio.Future to wait for the modal result in this worker
        # without blocking the App message pump.
        loop = asyncio.get_running_loop()
        auth_future: asyncio.Future[AuthResult | None] = loop.create_future()

        def _on_auth_done(result: AuthResult | None) -> None:
            if not auth_future.done():
                loop.call_soon_threadsafe(auth_future.set_result, result)

        self.app.push_screen(
            AuthPromptScreen(
                provider,
                env_var,
                reason=f"Required to use {spec}",
            ),
            _on_auth_done,
        )

        result = await auth_future
        return result is AuthResult.SAVED

    async def _switch_model(self, spec: str, effort: str | None = None) -> None:
        """Switch the active model, checking auth if needed.

        Package installation is NOT checked here — callers are responsible for
        ensuring the provider package is installed before calling this method
        (either via the model selector's install flow, or because the package
        was already present).
        """
        if ":" in spec:
            provider = spec.split(":", 1)[0]
        else:
            from dcoder.model.factory import detect_provider
            provider = detect_provider(spec) or "openai"

        # Check auth before switching
        auth_ok = await self._prompt_model_auth_if_needed(spec)
        if not auth_ok:
            return

        await self._finalize_model_switch(spec)

    async def _finalize_model_switch(self, spec: str, effort: str | None = None) -> None:
        """Perform the actual model switch and persist to recents.

        This is the final step after package installation and auth checks have
        passed. Sets the model, updates the status bar, and persists to recents.
        """
        from dcoder.model.config import save_recent_model, apply_stored_credentials

        provider = spec.split(":", 1)[0] if ":" in spec else ""
        if provider:
            apply_stored_credentials(provider)

        import os
        os.environ["DCODER_SERVER_MODEL"] = spec
        os.environ["DCODER_MODEL_NAME"] = spec
        self._model = spec
        if effort is not None:
            self._reasoning_effort = effort
            os.environ["DCODER_REASONING_EFFORT"] = effort
            settings_obj = getattr(self, "settings", None)
            if settings_obj:
                settings_obj.reasoning_effort = effort

        eff_display = effort or getattr(self, "_reasoning_effort", "") or ""

        if self._adapter:
            self._adapter._stats.model = spec
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.set_model(spec, effort=eff_display)
        except NoMatches:
            pass

        # Persist to recent models
        save_recent_model(spec)

        msg = f"Switched model to `{spec}`"
        if eff_display:
            msg += f" (thinking level: `{eff_display}`)"
        await self._mount_message(
            SystemMessage(msg)
        )

    # ── Effort Selector Integration ───────────────────────

    async def _show_effort_selector(self) -> None:
        """Open the interactive reasoning effort picker modal."""
        from dcoder.model.reasoning import (
            default_effort_for_model,
            supported_efforts_for_model,
        )
        from dcoder.ui.effort_selector import EffortSelectorScreen

        model_spec = self._model or "default"
        efforts = supported_efforts_for_model(model_spec) or ("low", "medium", "high")
        current_eff = getattr(self, "_reasoning_effort", None) or getattr(getattr(self, "settings", None), "reasoning_effort", None)
        default_eff = default_effort_for_model(model_spec) or "high"

        screen = EffortSelectorScreen(
            model_spec=model_spec,
            efforts=efforts,
            current_effort=current_eff,
            default_effort=default_eff,
        )

        def _on_effort_selected(result: str | None) -> None:
            if result is not None:
                self.run_worker(self._set_effort_override(result))

        self.push_screen(screen, _on_effort_selected)

    async def _set_effort_override(self, effort: str) -> None:
        """Apply reasoning effort override and update UI."""
        import os
        from dcoder.ui.messages import SystemMessage
        from dcoder.ui.status import StatusBar

        model_spec = self._model or "default"

        if effort.lower() in {"clear", "reset"}:
            self._reasoning_effort = None
            os.environ.pop("DCODER_REASONING_EFFORT", None)
            settings_obj = getattr(self, "settings", None)
            if settings_obj:
                settings_obj.reasoning_effort = None
            try:
                sb = self.query_one("#status-bar", StatusBar)
                sb.set_model(model_spec, effort="")
            except Exception:
                pass
            await self._mount_message(SystemMessage(f"Reasoning effort override cleared for `{model_spec}`."))
            return

        self._reasoning_effort = effort
        os.environ["DCODER_REASONING_EFFORT"] = effort
        settings_obj = getattr(self, "settings", None)
        if settings_obj:
            settings_obj.reasoning_effort = effort

        try:
            sb = self.query_one("#status-bar", StatusBar)
            sb.set_model(model_spec, effort=effort)
        except Exception:
            pass

        await self._mount_message(SystemMessage(f"Reasoning effort for `{model_spec}` set to `{effort}`."))

    # ── Agent Selector Integration ────────────────────────

    async def _show_agent_selector(self) -> None:
        """Open the interactive agent picker modal."""
        from dcoder.agent.config import get_available_agent_names, load_default_agent

        agent_names = get_available_agent_names()
        default_agent = load_default_agent()

        def _on_agent_selected(result: str | None) -> None:
            """Callback when the agent selector is dismissed."""
            if result is not None and result != self._assistant_id:
                self._switch_agent(result)
            # Refocus input
            if self._chat_input:
                self._chat_input.focus()

        from dcoder.ui.agent_selector import AgentSelectorScreen

        screen = AgentSelectorScreen(
            current_agent=self._assistant_id,
            agent_names=agent_names,
            default_agent=default_agent,
        )
        self.push_screen(screen, _on_agent_selected)

    def _switch_agent(self, agent_name: str) -> None:
        """Switch to a different agent and start a new thread.

        Clears the chat, updates the assistant_id, creates a new thread,
        and posts a confirmation message.

        Args:
            agent_name: The agent to switch to.
        """
        import uuid

        if agent_name == self._assistant_id:
            return

        # Guard: don't switch while agent is running
        if self._agent_running or self._shell_running:
            self.notify(
                "Cannot switch agents while a task is running. "
                "Interrupt or wait for it to finish first.",
                severity="warning",
            )
            return

        # Update identity
        old_agent = self._assistant_id
        self._assistant_id = agent_name

        # Clear chat and start new thread
        self._pending_messages.clear()
        self._queued_widgets.clear()
        try:
            messages = self.query_one("#messages", MessageList)
            messages.clear()
        except NoMatches:
            pass

        self._agent_thread_id = str(uuid.uuid4())

        # Update adapter if present
        if self._adapter:
            self._adapter._assistant_id = agent_name

        # Update status bar
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.set_status("Ready")
        except NoMatches:
            pass

        # Post confirmation
        self.call_later(
            self._mount_message,
            SystemMessage(f"Switched to {agent_name}. New thread started."),
        )

        logger.info("Agent switched: %s → %s", old_agent, agent_name)

    # ── Plugin Manager ───────────────────────────────────

    async def _show_plugin_manager(self) -> None:
        """Push the plugin manager modal screen for /plugins."""
        from dcoder.ui.plugin_manager import PluginManagerScreen

        mcp_info = self.get_mcp_servers() if hasattr(self, "get_mcp_servers") else ()
        screen = PluginManagerScreen(mcp_server_info=mcp_info)
        self.push_screen(screen)

    # ── Skills Viewer ────────────────────────────────────

    def _open_skills_viewer(self) -> None:
        """Push the interactive skills viewer modal screen."""
        from dcoder.ui.skills_viewer import SkillsViewerScreen

        skills = self.get_discovered_skills()
        self.push_screen(SkillsViewerScreen(skills=skills))

    # ── Goal Review ──────────────────────────────────────

    def _open_goal_review(self, objective: str, rubric: str) -> None:
        """Push the goal review modal for user approval of generated rubric."""
        from dcoder.ui.goal_review import GoalReviewScreen

        def _on_review_result(result: str | None) -> None:
            """Handle the review decision."""
            from dcoder.commands.power.goal import get_goal_state

            state = get_goal_state(self)

            if result == "accept":
                state.objective = state.pending_objective or objective
                state.status = "active"
                state.rubric = state.pending_rubric or rubric
                state.pending_objective = None
                state.pending_rubric = None
                from dcoder.commands.power.goal import GoalHandler
                GoalHandler._sync_status_rubric(self, state)
            elif result == "reject":
                state.pending_objective = None
                state.pending_rubric = None
                from dcoder.commands.power.goal import GoalHandler
                GoalHandler._sync_status_rubric(self, state)
            # else: cancelled — leave pending state for retry

        screen = GoalReviewScreen(objective, rubric)
        self.push_screen(screen, callback=_on_review_result)



    # ── Skill Command ────────────────────────────────────

    async def _handle_skill_command(self, command: str) -> None:
        """Handle a /skill:<name> command by delegating to the power handler.

        This method is called by convenience aliases like /remember and
        /skill-creator that rewrite to /skill: commands.
        """
        from dcoder.commands._base import CommandContext
        from dcoder.commands.power.skill_invoke import SkillInvokeHandler
        from dcoder.skills.invocation import parse_skill_command

        skill_name, args = parse_skill_command(command)
        ctx = CommandContext(
            app=self,
            raw_command=command,
            args=f"{skill_name} {args}".strip() if skill_name else "",
        )
        handler = SkillInvokeHandler()
        await handler.execute(ctx)

    # ── Exit ─────────────────────────────────────────────


    def exit(
        self,
        result: Any = None,
        return_code: int = 0,
        message: Any = None,
    ) -> None:
        """Exit the app after cleaning up background resources."""
        self._exit = True
        self._pending_messages.clear()
        self._queued_widgets.clear()
        if self._adapter:
            self._adapter.cancel()
        if self._server_proc is not None:
            try:
                self._server_proc.stop()
            except Exception:
                logger.debug("Failed to stop server process during exit", exc_info=True)
        # Return thread_id so the CLI can print a resume hint
        if result is None:
            result = self._agent_thread_id
        super().exit(result=result, return_code=return_code, message=message)

    def action_quit_app(self) -> None:
        self.exit()
