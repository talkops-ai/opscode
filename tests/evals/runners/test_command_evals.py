"""Eval runner — pytest-driven runner that loads YAML datasets and runs eval scenarios."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.evals.evaluators.trajectory_evaluator import (
    evaluate_output_structure,
    evaluate_tool_sequence,
)


DATASETS_DIR = Path(__file__).parent.parent / "datasets"


def load_dataset(name: str) -> list[dict]:
    """Load a YAML eval dataset by name."""
    path = DATASETS_DIR / f"{name}.yaml"
    if not path.exists():
        pytest.skip(f"Dataset {name}.yaml not found")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("scenarios", [])


class TestTrajectoryEvaluator:
    """Verify the trajectory evaluator itself works correctly."""

    def test_perfect_match(self):
        actual = [{"name": "read_file"}, {"name": "write_file"}]
        expected = ["read_file", "write_file"]
        result = evaluate_tool_sequence(actual, expected)
        assert result.matched is True
        assert result.score == 1.0

    def test_missing_tool(self):
        actual = [{"name": "read_file"}]
        expected = ["read_file", "write_file"]
        result = evaluate_tool_sequence(actual, expected)
        assert result.matched is False
        assert result.score == 0.5
        assert "write_file" in result.missing_tools

    def test_strict_order_match(self):
        actual = [{"name": "read_file"}, {"name": "write_file"}, {"name": "delete"}]
        expected = ["read_file", "write_file"]
        result = evaluate_tool_sequence(actual, expected, strict_order=True)
        assert result.matched is True
        assert result.score == 1.0

    def test_strict_order_mismatch(self):
        actual = [{"name": "write_file"}, {"name": "read_file"}]
        expected = ["read_file", "write_file"]
        result = evaluate_tool_sequence(actual, expected, strict_order=True)
        # write_file comes before read_file, so only one can match in subsequence
        assert result.score < 1.0

    def test_empty_expected(self):
        actual = [{"name": "read_file"}]
        result = evaluate_tool_sequence(actual, [])
        assert result.matched is True
        assert result.score == 1.0


class TestOutputStructureEvaluator:
    """Verify the output structure evaluator works correctly."""

    def test_all_required_present(self):
        output = {"success": True, "message": "done", "data": {}}
        result = evaluate_output_structure(output, ["success", "message"])
        assert result.matched is True
        assert result.score == 1.0

    def test_missing_key(self):
        output = {"success": True}
        result = evaluate_output_structure(output, ["success", "message"])
        assert result.matched is False
        assert "message" in result.missing_tools

    def test_forbidden_key_present(self):
        output = {"success": True, "internal_error": "leak"}
        result = evaluate_output_structure(
            output, ["success"], forbidden_keys=["internal_error"]
        )
        assert result.matched is False


class TestCommandRoutingDataset:
    """Verify the command routing dataset loads and has valid structure."""

    def test_dataset_loads(self):
        scenarios = load_dataset("command_routing")
        assert len(scenarios) > 0

    def test_all_scenarios_have_required_fields(self):
        scenarios = load_dataset("command_routing")
        for scenario in scenarios:
            assert "name" in scenario, f"Scenario missing 'name': {scenario}"
            assert "input" in scenario, f"Scenario {scenario.get('name')} missing 'input'"
            assert "expected" in scenario, f"Scenario {scenario.get('name')} missing 'expected'"

    def test_all_scenarios_have_success_field(self):
        scenarios = load_dataset("command_routing")
        for scenario in scenarios:
            assert "success" in scenario["expected"], (
                f"Scenario {scenario['name']} missing 'expected.success'"
            )
