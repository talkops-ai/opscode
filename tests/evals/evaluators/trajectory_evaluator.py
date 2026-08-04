"""Trajectory evaluator — deterministic checks on agent tool call sequences."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrajectoryMatch:
    """Result of comparing an actual trajectory against expectations."""

    matched: bool
    score: float  # 0.0 to 1.0
    expected_tools: list[str]
    actual_tools: list[str]
    missing_tools: list[str] = field(default_factory=list)
    extra_tools: list[str] = field(default_factory=list)
    details: str = ""


def evaluate_tool_sequence(
    actual_tool_calls: list[dict[str, Any]],
    expected_tool_names: list[str],
    *,
    strict_order: bool = False,
) -> TrajectoryMatch:
    """Evaluate whether the agent called the expected tools.

    Args:
        actual_tool_calls: List of tool call dicts with at least a "name" key.
        expected_tool_names: List of tool names expected in the trajectory.
        strict_order: If True, tools must appear in the exact order listed.

    Returns:
        A TrajectoryMatch with score and diagnostics.
    """
    actual_names = [tc.get("name", "") for tc in actual_tool_calls]

    if strict_order:
        # Check if expected is a subsequence of actual
        idx = 0
        matched_count = 0
        for expected in expected_tool_names:
            while idx < len(actual_names):
                if actual_names[idx] == expected:
                    matched_count += 1
                    idx += 1
                    break
                idx += 1
            else:
                break

        score = matched_count / len(expected_tool_names) if expected_tool_names else 1.0
        matched = matched_count == len(expected_tool_names)
    else:
        # Set-based matching
        actual_set = set(actual_names)
        expected_set = set(expected_tool_names)
        missing = expected_set - actual_set
        extra = actual_set - expected_set

        if not expected_set:
            score = 1.0
        else:
            score = (len(expected_set) - len(missing)) / len(expected_set)

        matched = len(missing) == 0

    missing_tools = [t for t in expected_tool_names if t not in actual_names]
    extra_tools = [t for t in actual_names if t not in expected_tool_names]

    return TrajectoryMatch(
        matched=matched,
        score=score,
        expected_tools=expected_tool_names,
        actual_tools=actual_names,
        missing_tools=missing_tools,
        extra_tools=extra_tools,
        details=f"Score: {score:.2f}, Missing: {missing_tools}, Extra: {extra_tools}",
    )


def evaluate_output_structure(
    output: dict[str, Any],
    required_keys: list[str],
    *,
    forbidden_keys: list[str] | None = None,
) -> TrajectoryMatch:
    """Evaluate whether an agent output contains required structural keys.

    Args:
        output: The agent's output dict.
        required_keys: Keys that must be present.
        forbidden_keys: Keys that must NOT be present.

    Returns:
        A TrajectoryMatch with score based on key presence.
    """
    present = [k for k in required_keys if k in output]
    missing = [k for k in required_keys if k not in output]
    forbidden_present = [k for k in (forbidden_keys or []) if k in output]

    total_checks = len(required_keys) + len(forbidden_keys or [])
    passed = len(present) + (len(forbidden_keys or []) - len(forbidden_present))
    score = passed / total_checks if total_checks > 0 else 1.0
    matched = not missing and not forbidden_present

    return TrajectoryMatch(
        matched=matched,
        score=score,
        expected_tools=required_keys,
        actual_tools=list(output.keys()),
        missing_tools=missing,
        extra_tools=forbidden_present,
        details=f"Required: {required_keys}, Missing: {missing}, Forbidden present: {forbidden_present}",
    )
