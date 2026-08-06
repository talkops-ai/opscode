"""Unit tests for dcoder.config.metadata trace metadata helpers."""

from pathlib import Path
from unittest.mock import patch

from dcoder._version import __version__
from dcoder.config.metadata import (
    CODING_AGENT_INTEGRATION,
    CODING_AGENT_PURPOSE,
    CODING_AGENT_RUNTIME,
    CODING_AGENT_TRACE_SCHEMA_VERSION,
    build_coding_agent_metadata,
    build_stream_config,
)
from dcoder.utils.git import RepositoryMetadata


def test_build_coding_agent_metadata_basic():
    metadata = build_coding_agent_metadata(
        thread_id="test-thread-123",
        cwd="/tmp",
    )

    assert metadata["ls_agent_purpose"] == CODING_AGENT_PURPOSE
    assert metadata["ls_integration"] == CODING_AGENT_INTEGRATION
    assert metadata["ls_agent_runtime"] == CODING_AGENT_RUNTIME
    assert metadata["ls_trace_schema_version"] == CODING_AGENT_TRACE_SCHEMA_VERSION
    assert metadata["ls_integration_version"] == __version__
    assert metadata["ls_agent_runtime_version"] == __version__
    assert metadata["thread_id"] == "test-thread-123"
    assert metadata["cwd"] == "/tmp"


def test_build_coding_agent_metadata_turn_markers_and_sandbox():
    metadata = build_coding_agent_metadata(
        thread_id="thread-456",
        turn_id="turn-789",
        turn_number=3,
        sandbox_type="docker",
        user_id="usr_001",
    )

    assert metadata["turn_id"] == "turn-789"
    assert metadata["turn_number"] == 3
    assert metadata["sandbox_type"] == "docker"
    assert metadata["user_id"] == "usr_001"


def test_build_coding_agent_metadata_with_git_repo(tmp_path: Path):
    with (
        patch("dcoder.config.metadata.resolve_git_remote_url", return_value="git@github.com:org/repo.git"),
        patch("dcoder.config.metadata.parse_repository_metadata", return_value=RepositoryMetadata("https://github.com/org/repo", "github", "org/repo")),
        patch("dcoder.config.metadata.resolve_git_branch", return_value="feature/test"),
        patch("dcoder.config.metadata.resolve_git_commit_sha", return_value="a" * 40),
    ):
        metadata = build_coding_agent_metadata(
            thread_id="thread-git",
            cwd=tmp_path,
        )

        assert metadata["repository_url"] == "https://github.com/org/repo"
        assert metadata["repository_provider"] == "github"
        assert metadata["repository_name"] == "org/repo"
        assert metadata["git_branch"] == "feature/test"
        assert metadata["git_commit_sha"] == "a" * 40


def test_build_stream_config_structure():
    config = build_stream_config(
        thread_id="stream-thread-1",
        assistant_id="agent",
        turn_id="turn-uuid-1",
        turn_number=1,
        auto_approve=True,
    )

    assert config["configurable"] == {"thread_id": "stream-thread-1"}

    metadata = config["metadata"]
    assert metadata["thread_id"] == "stream-thread-1"
    assert metadata["dcoder_agent_name"] == "agent"
    assert metadata["agent_name"] == "agent"
    assert metadata["turn_id"] == "turn-uuid-1"
    assert metadata["turn_number"] == 1
    assert metadata["dcoder_auto_approve"] is True
    assert metadata["lc_versions"] == {"dcoder": __version__}
    assert "updated_at" in metadata
    assert "dcoder_term_program" in metadata
