"""Trace metadata generation for LangSmith and telemetry correlation.

Implements the `coding-agent-v1` contract for DCoder: identity block, plugin/runtime
versions, turn markers, and dynamic repository/git/cwd attribution.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dcoder._version import __version__
from dcoder.config.env_vars import EXPERIMENTAL, USER_ID, is_env_truthy
from dcoder.utils.git import (
    RepositoryMetadata,
    parse_repository_metadata,
    resolve_git_branch,
    resolve_git_commit_sha,
    resolve_git_remote_url,
)

logger = logging.getLogger(__name__)

# coding-agent-v1 contract literals.
CODING_AGENT_PURPOSE = "coding"
CODING_AGENT_INTEGRATION = "deepagents-code"
CODING_AGENT_RUNTIME = "Deep Agents Code"
CODING_AGENT_TRACE_SCHEMA_VERSION = "coding-agent-v1"

_git_branch_cache: dict[str, str | None] = {}
_repo_metadata_cache: dict[str, RepositoryMetadata | None] = {}


def _get_git_branch(cwd_str: str) -> str | None:
    if cwd_str in _git_branch_cache:
        return _git_branch_cache[cwd_str]
    branch: str | None = None
    try:
        raw_branch = resolve_git_branch(cwd_str)
        branch = raw_branch if raw_branch else None
    except OSError:
        logger.debug("Could not determine git branch for %s", cwd_str, exc_info=True)
    _git_branch_cache[cwd_str] = branch
    return branch


def _get_git_commit_sha(cwd_str: str) -> str | None:
    try:
        raw_sha = resolve_git_commit_sha(cwd_str)
        return raw_sha if raw_sha else None
    except OSError:
        logger.debug("Could not determine git commit sha for %s", cwd_str, exc_info=True)
        return None


def _get_repository_metadata(cwd_str: str) -> RepositoryMetadata | None:
    if cwd_str in _repo_metadata_cache:
        return _repo_metadata_cache[cwd_str]
    repo: RepositoryMetadata | None = None
    try:
        remote_url = resolve_git_remote_url(cwd_str)
        if remote_url:
            repo = parse_repository_metadata(remote_url)
    except OSError:
        logger.debug("Could not determine git remote for %s", cwd_str, exc_info=True)
    _repo_metadata_cache[cwd_str] = repo
    return repo


def _get_deepagents_version() -> str | None:
    try:
        import deepagents
        return getattr(deepagents, "__version__", None)
    except ImportError:
        try:
            import importlib.metadata
            return importlib.metadata.version("deepagents")
        except Exception:
            return None


def build_coding_agent_metadata(
    *,
    thread_id: str,
    turn_id: str | None = None,
    turn_number: int | None = None,
    cwd: str | Path | None = None,
    git_branch: str | None = None,
    sandbox_type: str | None = None,
    user_id: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    """Build the shared coding-agent-v1 trace-metadata block."""
    if cwd is None:
        try:
            cwd_str = str(Path.cwd())
        except OSError:
            cwd_str = ""
    else:
        cwd_str = str(cwd)

    metadata: dict[str, Any] = {
        "ls_agent_purpose": CODING_AGENT_PURPOSE,
        "ls_integration": CODING_AGENT_INTEGRATION,
        "ls_agent_runtime": CODING_AGENT_RUNTIME,
        "thread_id": thread_id,
        "ls_trace_schema_version": CODING_AGENT_TRACE_SCHEMA_VERSION,
        "ls_integration_version": __version__,
        "ls_agent_runtime_version": __version__,
    }

    if turn_id:
        metadata["turn_id"] = turn_id
    if turn_number is not None:
        metadata["turn_number"] = turn_number

    if reasoning_effort:
        metadata["reasoning_effort"] = reasoning_effort

    if cwd_str:
        metadata["cwd"] = cwd_str
        repo = _get_repository_metadata(cwd_str)
        if repo is not None:
            metadata["repository_url"] = repo.url
            metadata["repository_provider"] = repo.provider
            metadata["repository_name"] = repo.name

        effective_branch = git_branch or _get_git_branch(cwd_str)
        if effective_branch:
            metadata["git_branch"] = effective_branch

        commit_sha = _get_git_commit_sha(cwd_str)
        if commit_sha:
            metadata["git_commit_sha"] = commit_sha

    if user_id:
        metadata["user_id"] = user_id
    if sandbox_type and sandbox_type != "none":
        metadata["sandbox_type"] = sandbox_type

    return metadata


def build_stream_config(
    thread_id: str,
    assistant_id: str | None = None,
    *,
    sandbox_type: str | None = None,
    turn_id: str | None = None,
    turn_number: int | None = None,
    approval_mode: str | None = None,
    approval_mode_key: str | None = None,
    auto_approve: bool = False,
    cwd: str | Path | None = None,
    reasoning_effort: str | None = "medium",
) -> dict[str, Any]:
    """Build the LangGraph stream config dict including coding-agent-v1 metadata."""
    if cwd is None:
        try:
            effective_cwd = str(Path.cwd())
        except OSError:
            logger.warning("Could not determine working directory", exc_info=True)
            effective_cwd = ""
    else:
        effective_cwd = str(cwd)

    effective_user_id = os.environ.get(USER_ID) or None
    effective_branch = _get_git_branch(effective_cwd) if effective_cwd else None

    metadata: dict[str, Any] = build_coding_agent_metadata(
        thread_id=thread_id,
        turn_id=turn_id,
        turn_number=turn_number,
        cwd=effective_cwd,
        git_branch=effective_branch,
        sandbox_type=sandbox_type,
        user_id=effective_user_id,
        reasoning_effort=reasoning_effort,
    )

    if is_env_truthy(EXPERIMENTAL):
        metadata["dcoder_experimental"] = True

    if auto_approve:
        metadata["dcoder_auto_approve"] = True

    metadata["lc_versions"] = {
        "dcoder": __version__,
    }

    deepagents_version = _get_deepagents_version()
    if deepagents_version is not None:
        metadata["dcoder_client_deepagents_version"] = deepagents_version

    metadata["dcoder_term_program"] = os.environ.get("DCODER_TERM_PROGRAM") or os.environ.get(
        "TERM_PROGRAM", "vscode"
    )

    if assistant_id:
        metadata.update(
            {
                "dcoder_agent_name": assistant_id,
                "agent_name": assistant_id,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )

    return {
        "configurable": {"thread_id": thread_id},
        "metadata": metadata,
    }
