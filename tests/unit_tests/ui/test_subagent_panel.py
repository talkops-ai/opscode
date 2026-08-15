"""Unit tests for SubagentPanel, _Phase, and _SubagentRecord."""

import time
import pytest
from dcoder.ui.widgets.subagent_panel import (
    SubagentPanel,
    _Phase,
    _SubagentRecord,
    _format_timing,
    sanitize_control_chars,
)


def test_subagent_record_elapsed():
    """Verify elapsed time calculation for subagent record."""
    start = time.monotonic() - 2.5
    record = _SubagentRecord(id="sub-1", label="run task", started_monotonic=start)
    assert record.elapsed_seconds() >= 2.4

    # Completed record uses duration_ms
    record.duration_ms = 1500
    assert record.elapsed_seconds() == 1.5


def test_phase_aggregation():
    """Verify phase record management, counts, and status checks."""
    phase = _Phase(eval_id="eval-1", index=1)
    r1 = _SubagentRecord(id="s1", label="task 1", status="running")
    r2 = _SubagentRecord(id="s2", label="task 2", status="done", duration_ms=2000)

    phase.add(r1)
    phase.add(r2)

    assert len(phase.records) == 2
    assert phase.any_running() is True
    assert phase.all_terminal() is False

    done, total = phase.counts()
    assert done == 1
    assert total == 2

    # Finish r1
    r1.status = "done"
    r1.duration_ms = 1000
    assert phase.any_running() is False
    assert phase.all_terminal() is True


def test_format_timing_helper():
    """Verify stable timing string formatting."""
    assert _format_timing(5.2) == "5.2s"
    assert _format_timing(120.0) == "2m0s" or _format_timing(120.0) == "2m"


def test_sanitize_control_chars():
    """Verify control char sanitization."""
    raw = "line1\nline2\x1b[31mred\x1b[0m"
    clean = sanitize_control_chars(raw)
    assert "\n" not in clean


def test_subagent_panel_event_lifecycle():
    """Verify SubagentPanel handling start and complete events."""
    panel = SubagentPanel()
    
    start_event = {
        "type": "subagent",
        "phase": "start",
        "id": "sub-100",
        "eval_id": "eval-abc",
        "subagent_type": "researcher",
        "description": "Analyze repository structure",
    }
    panel.on_subagent_event(start_event)
    
    assert "eval-abc" in panel._phases
    phase = panel._phases["eval-abc"]
    assert len(phase.records) == 1
    assert phase.records["sub-100"].status == "running"

    complete_event = {
        "type": "subagent",
        "phase": "complete",
        "id": "sub-100",
        "eval_id": "eval-abc",
        "duration_ms": 3200,
    }
    panel.on_subagent_event(complete_event)
    assert phase.records["sub-100"].status == "done"
    assert phase.records["sub-100"].duration_ms == 3200
