"""Output evaluator — structural and content validation for agent outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OutputEvalResult:
    """Result of evaluating an agent output against expected patterns."""

    matched: bool
    score: float  # 0.0 to 1.0
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    details: str = ""


def evaluate_contains(
    output: str,
    must_contain: list[str],
    must_not_contain: list[str] | None = None,
    *,
    case_sensitive: bool = False,
) -> OutputEvalResult:
    """Evaluate whether output text contains required patterns.

    Args:
        output: The agent's text output.
        must_contain: Patterns that must appear in the output.
        must_not_contain: Patterns that must NOT appear in the output.
        case_sensitive: Whether matching is case-sensitive.

    Returns:
        OutputEvalResult with score and diagnostics.
    """
    checks_passed: list[str] = []
    checks_failed: list[str] = []

    compare_text = output if case_sensitive else output.lower()

    for pattern in must_contain:
        compare_pattern = pattern if case_sensitive else pattern.lower()
        if compare_pattern in compare_text:
            checks_passed.append(f"Contains '{pattern}'")
        else:
            checks_failed.append(f"Missing '{pattern}'")

    for pattern in (must_not_contain or []):
        compare_pattern = pattern if case_sensitive else pattern.lower()
        if compare_pattern in compare_text:
            checks_failed.append(f"Should not contain '{pattern}'")
        else:
            checks_passed.append(f"Correctly omits '{pattern}'")

    total = len(checks_passed) + len(checks_failed)
    score = len(checks_passed) / total if total > 0 else 1.0

    return OutputEvalResult(
        matched=len(checks_failed) == 0,
        score=score,
        checks_passed=checks_passed,
        checks_failed=checks_failed,
        details=f"Passed: {len(checks_passed)}/{total}",
    )


def evaluate_command_result(
    result: dict[str, Any],
    expected: dict[str, Any],
) -> OutputEvalResult:
    """Evaluate a CommandResult dict against expected values.

    Args:
        result: The actual CommandResult as a dict (success, message, etc.).
        expected: Expected values to check.

    Returns:
        OutputEvalResult with score and diagnostics.
    """
    checks_passed: list[str] = []
    checks_failed: list[str] = []

    # Check success field
    if "success" in expected:
        if result.get("success") == expected["success"]:
            checks_passed.append(f"success={expected['success']}")
        else:
            checks_failed.append(
                f"Expected success={expected['success']}, got {result.get('success')}"
            )

    # Check contains patterns in message
    if "contains" in expected and result.get("message"):
        message = result["message"]
        for pattern in expected["contains"]:
            if pattern.lower() in message.lower():
                checks_passed.append(f"Message contains '{pattern}'")
            else:
                checks_failed.append(f"Message missing '{pattern}'")

    # Check command routing
    if "command" in expected:
        if result.get("command") == expected["command"]:
            checks_passed.append(f"Routed to command '{expected['command']}'")
        else:
            checks_failed.append(
                f"Expected command '{expected['command']}', got '{result.get('command')}'"
            )

    total = len(checks_passed) + len(checks_failed)
    score = len(checks_passed) / total if total > 0 else 1.0

    return OutputEvalResult(
        matched=len(checks_failed) == 0,
        score=score,
        checks_passed=checks_passed,
        checks_failed=checks_failed,
        details=f"Passed: {len(checks_passed)}/{total}",
    )
