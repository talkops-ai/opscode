"""Unit tests for rubric evaluator — path validation and grader tool constraints."""

import pytest

from dcoder.rubrics.evaluator import (
    _RUBRIC_GRADER_READ_FILE_PREFIX,
    _validate_rubric_grader_read_path,
)


class TestValidateRubricGraderReadPath:
    """Tests for _validate_rubric_grader_read_path."""

    def test_valid_path_under_prefix(self):
        path = "/large_tool_results/result_001.txt"
        assert _validate_rubric_grader_read_path(path) is None

    def test_valid_nested_path(self):
        path = "/large_tool_results/subdir/result.json"
        assert _validate_rubric_grader_read_path(path) is None

    def test_rejects_path_outside_prefix(self):
        path = "/etc/passwd"
        error = _validate_rubric_grader_read_path(path)
        assert error is not None
        assert "only read files under" in error

    def test_rejects_home_directory(self):
        path = "/home/user/.ssh/id_rsa"
        error = _validate_rubric_grader_read_path(path)
        assert error is not None

    def test_rejects_dot_dot_traversal(self):
        path = "/large_tool_results/../../etc/passwd"
        error = _validate_rubric_grader_read_path(path)
        assert error is not None
        assert "Invalid path" in error

    def test_rejects_tilde_traversal(self):
        path = "/large_tool_results/~/secret"
        error = _validate_rubric_grader_read_path(path)
        assert error is not None
        assert "Invalid path" in error

    def test_normalizes_backslashes(self):
        path = "\\large_tool_results\\result.txt"
        # After normalization, should start with /large_tool_results/
        result = _validate_rubric_grader_read_path(path)
        assert result is None

    def test_prefix_constant_exists(self):
        assert _RUBRIC_GRADER_READ_FILE_PREFIX == "/large_tool_results/"
