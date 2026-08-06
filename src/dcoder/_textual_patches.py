r"""Runtime patches over Textual internals, imported for side effect.

Reference: deepagents_code/_textual_patches.py

This module hosts four independent best-effort patches over private Textual
APIs. Each guards its own import/assignment and degrades to stock Textual
behavior (logging a warning) if the targeted internals move, so they have
separate lifecycles.

1. Alt-modifier preservation on legacy `ESC + <byte>` sequences. Upstream
    `XTermParser._sequence_to_key_events` drops the `alt` flag on the
    tuple-branch fast path, so VSCode's `sendSequence` shift+enter binding
    (which writes `\x1b\r` to the PTY) arrives as bare `enter` instead of
    `alt+enter`. Tracked in Textualize/textual#6378.
"""

from __future__ import annotations

import logging
import re
from inspect import isawaitable
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text
from textual import __version__ as _textual_version
from textual.content import Content
from textual.geometry import Offset
from textual.selection import Selection

if TYPE_CHECKING:
    from collections.abc import Iterable

    from textual.events import Click, Event
    from textual.screen import Screen
    from textual.selection import SelectState
    from textual.widget import Widget

logger = logging.getLogger(__name__)

_ESC_PREFIX_LEN = 2
_DOUBLE_CLICK_CHAIN = 2
_TRIPLE_CLICK_CHAIN = 3
_DCODER_WORD_SELECT_ACTIVE = "_dcoder_word_select_active"

try:
    from textual import events
    from textual._ansi_sequences import (  # noqa: PLC2701
        ANSI_SEQUENCES_KEYS,
        IGNORE_SEQUENCE,
    )
    from textual._xterm_parser import XTermParser  # noqa: PLC2701

    _original = XTermParser._sequence_to_key_events
except (ImportError, AttributeError) as exc:  # pragma: no cover - defensive
    logger.warning("Textual keyboard parser patch skipped: %s", exc)
else:
    _KITTY_LOCK_KEY_CODES = frozenset({"57358", "57359", "57360"})
    _KITTY_LOCK_KEY_NAMES = {
        "57358": "caps_lock",
        "57359": "scroll_lock",
        "57360": "num_lock",
    }

    _KITTY_KEY_SEQUENCE = re.compile(r"\x1b\[(\d+)[\d;:]*u")
    _KITTY_SUBFIELD_KEY = re.compile(r"\x1b\[[\d;:]*:[\d;:]*[u~ABCDEFHPQRS]")
    _KITTY_CSI_U = re.compile(
        r"\x1b\[(\d+)(?::\d+)*(?:;(\d+)[\d:]*)?(?:;(\d+)[\d:]*)?u"
    )
    _ASCII_UPPER_A = 65
    _ASCII_UPPER_Z = 90
    _REAL_MODIFIER_MASK = 0b111111

    def _spurious_caps_lock(sequence: str) -> bool:
        match = _KITTY_CSI_U.fullmatch(sequence)
        if match is None:
            return False
        code = int(match.group(1))
        if not _ASCII_UPPER_A <= code <= _ASCII_UPPER_Z:
            return False
        modifier_bits = (int(match.group(2)) - 1) if match.group(2) else 0
        has_text = match.group(3) is not None
        return modifier_bits & _REAL_MODIFIER_MASK == 0 and not has_text

    def _strip_kitty_subfields(sequence: str) -> str:
        body, terminator = sequence[2:-1], sequence[-1]
        fields = body.split(";")
        fields[:2] = [field.split(":", 1)[0] for field in fields[:2]]
        return f"\x1b[{';'.join(fields)}{terminator}"

    def _lock_key_event(sequence: str) -> events.Key | None:
        match = _KITTY_KEY_SEQUENCE.fullmatch(sequence)
        if match is None or match.group(1) not in _KITTY_LOCK_KEY_CODES:
            return None
        return events.Key(_KITTY_LOCK_KEY_NAMES[match.group(1)], None)

    def _emit_alt(keys: tuple, character: str | None) -> Iterable[events.Key]:
        for key in keys:
            yield events.Key(f"alt+{key.value}", character)

    def _sequence_to_key_events_with_alt(
        self: XTermParser, sequence: str, alt: bool = False
    ) -> Iterable[events.Key]:
        if (lock_event := _lock_key_event(sequence)) is not None:
            yield lock_event
            return
        if _spurious_caps_lock(sequence):
            yield events.Key("caps_lock", None)
            return
        if _KITTY_SUBFIELD_KEY.fullmatch(sequence):
            sequence = _strip_kitty_subfields(sequence)
        # Fast path: \x1b<byte> on first pass. Short-circuits the ~100 ms
        # escape-delay wait when both bytes arrive together.
        if not alt and len(sequence) == _ESC_PREFIX_LEN and sequence[0] == "\x1b":
            inner = ANSI_SEQUENCES_KEYS.get(sequence[1])
            if inner is not IGNORE_SEQUENCE and isinstance(inner, tuple):
                yield from _emit_alt(inner, None)
                return
        # Correctness fix (Textualize/textual#6378): preserve `alt` on the
        # reissue path for single-byte tuple mappings.
        if alt:
            keys = ANSI_SEQUENCES_KEYS.get(sequence)
            if keys is not IGNORE_SEQUENCE and isinstance(keys, tuple):
                character = sequence if len(sequence) == 1 else None
                yield from _emit_alt(keys, character)
                return
        yield from _original(self, sequence, alt=alt)

    try:
        setattr(XTermParser, "_sequence_to_key_events", _sequence_to_key_events_with_alt)
    except (AttributeError, TypeError) as exc:  # pragma: no cover - defensive
        logger.warning("Textual keyboard parser patch assignment rejected: %s", exc)


def _rendered_text(widget: Widget) -> str | None:
    visual = widget._render()
    if isinstance(visual, (Content, Text)):
        return str(visual)
    return None


def _word_bounds(text: str, offset: Offset) -> tuple[Offset, Offset] | None:
    lines = text.splitlines()
    if not lines:
        return None

    y = min(max(offset.y, 0), len(lines) - 1)
    line = lines[y]
    if not line:
        return None

    x = min(max(offset.x, 0), len(line))
    index = min(x, len(line) - 1)
    if line[index].isspace():
        if x == len(line) and x > 0 and not line[x - 1].isspace():
            index = x - 1
        else:
            return None

    start = index
    while start > 0 and not line[start - 1].isspace():
        start -= 1

    end = index + 1
    while end < len(line) and not line[end].isspace():
        end += 1

    return Offset(start, y), Offset(end, y)


def _word_selection(widget: Widget, selection: Selection) -> Selection | None:
    if selection.start is None or selection.end is None:
        return None

    text = _rendered_text(widget)
    if text is None:
        return None

    start, end = selection.start, selection.end
    if end.transpose < start.transpose:
        start, end = end, start

    start_bounds = _word_bounds(text, start)
    end_bounds = _word_bounds(text, end)
    if start_bounds is None and end_bounds is None:
        return None

    return Selection(
        start_bounds[0] if start_bounds is not None else start,
        end_bounds[1] if end_bounds is not None else end,
    )


def _select_word_at_click(widget: Widget, event: Click) -> bool:
    offset = event.get_content_offset(widget)
    if offset is None:
        return False

    text = _rendered_text(widget)
    if text is None:
        return False

    bounds = _word_bounds(text, offset)
    if bounds is None:
        widget.screen.clear_selection()
        return True

    widget.screen.selections = {widget: Selection(*bounds)}
    return True


try:
    from textual import events as _events
    from textual.screen import Screen as _Screen
    from textual.widget import Widget as _Widget

    _original_forward_event = _Screen._forward_event
    _original_watch_select_state = _Screen._watch__select_state
    _original_widget_on_click = _Widget._on_click
except (ImportError, AttributeError) as exc:  # pragma: no cover - defensive
    logger.warning(
        "Textual word-selection patch skipped (textual %s): %s",
        _textual_version,
        exc,
    )
else:

    def _is_word_select_start(screen: Screen, event: Event) -> bool:
        if not isinstance(event, _events.MouseDown) or screen.app.mouse_captured:
            return False

        last_offset = getattr(screen.app, "_click_chain_last_offset", None)
        last_time = getattr(screen.app, "_click_chain_last_time", None)
        if last_offset != event.screen_offset or last_time is None:
            return False

        if event.time - last_time > screen.app.CLICK_CHAIN_TIME_THRESHOLD:
            return False

        select_widget, select_offset = screen.get_widget_and_offset_at(event.x, event.y)
        return (
            select_widget is not None
            and select_widget.allow_select
            and screen.allow_select
            and screen.app.ALLOW_SELECT
            and select_offset is not None
        )

    def _forward_event_with_word_select(self: Screen, event: Event) -> None:
        if isinstance(event, _events.MouseDown):
            setattr(
                self,
                _DCODER_WORD_SELECT_ACTIVE,
                _is_word_select_start(self, event),
            )
        try:
            _original_forward_event(self, event)
        finally:
            if isinstance(event, _events.MouseUp):
                setattr(self, _DCODER_WORD_SELECT_ACTIVE, False)

    async def _watch_select_state_with_word_select(
        self: Screen,
        select_state: SelectState | None,
    ) -> None:
        result: Any = _original_watch_select_state(self, select_state)
        if isawaitable(result):
            await cast(Any, result)
        if not getattr(self, _DCODER_WORD_SELECT_ACTIVE, False):
            return

        selections = dict(self.selections)
        changed = False
        for widget, selection in selections.items():
            word_selection = _word_selection(widget, selection)
            if word_selection is None or word_selection == selection:
                continue
            selections[widget] = word_selection
            changed = True

        if changed:
            self.selections = selections

    async def _on_click_with_word_select(self: Widget, event: Click) -> None:
        if (
            event.widget is self
            and self.allow_select
            and self.screen.allow_select
            and self.app.ALLOW_SELECT
        ):
            if event.chain == _DOUBLE_CLICK_CHAIN and _select_word_at_click(
                self, event
            ):
                await self.broker_event("click", event)
                return
            if event.chain == _TRIPLE_CLICK_CHAIN:
                self.text_select_all()
                await self.broker_event("click", event)
                return

        await _original_widget_on_click(self, event)

    try:
        setattr(_Screen, "_forward_event", _forward_event_with_word_select)
        setattr(_Screen, "_watch__select_state", _watch_select_state_with_word_select)
        setattr(_Widget, "_on_click", _on_click_with_word_select)
    except (AttributeError, TypeError) as exc:  # pragma: no cover - defensive
        logger.warning(
            "Textual word-selection patch assignment rejected (textual %s): %s",
            _textual_version,
            exc,
        )


try:
    from textual.screen import Screen as _HitScreen

    _original_get_widget_and_offset_at = _HitScreen.get_widget_and_offset_at
except (ImportError, AttributeError) as exc:  # pragma: no cover - defensive
    logger.warning(
        "Textual detached-hit patch skipped (textual %s): %s",
        _textual_version,
        exc,
    )
else:

    def _get_widget_and_offset_at_attached(
        self: Screen,
        x: int,
        y: int,
    ) -> tuple[Widget | None, Offset | None]:
        widget, offset = _original_get_widget_and_offset_at(self, x, y)
        if (
            widget is not None
            and not isinstance(widget, _HitScreen)
            and (widget.parent is None or not widget.is_attached)
        ):
            return None, None
        return widget, offset

    try:
        setattr(_HitScreen, "get_widget_and_offset_at", _get_widget_and_offset_at_attached)
    except (AttributeError, TypeError) as exc:  # pragma: no cover - defensive
        logger.warning(
            "Textual detached-hit patch assignment rejected (textual %s): %s",
            _textual_version,
            exc,
        )
