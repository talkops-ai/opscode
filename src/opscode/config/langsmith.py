"""LangSmith tracing helpers and project URL resolution."""

from __future__ import annotations

import logging
import threading
from typing import Any

from opscode.config.settings import resolve_env_var

logger = logging.getLogger(__name__)

_LANGSMITH_URL_LOOKUP_TIMEOUT_SECONDS = 3.0
_langsmith_url_cache: tuple[str, str] | None = None


class LangSmithLookupError(Exception):
    """Base class for typed LangSmith project URL lookup failures."""


class LangSmithImportError(LangSmithLookupError):
    """The `langsmith` package is not installed."""


class LangSmithLookupTimeoutError(LangSmithLookupError):
    """The LangSmith project URL lookup exceeded its hard timeout."""


class LangSmithApiError(LangSmithLookupError):
    """The LangSmith SDK call raised — auth, 404, network, etc."""


class LangSmithProjectNotFoundError(LangSmithApiError):
    """The LangSmith project does not exist yet (lookup returned 404)."""


def _is_langsmith_not_found(exc: Exception) -> bool:
    """Whether a LangSmith SDK error indicates the project does not exist."""
    try:
        from langsmith.utils import LangSmithNotFoundError
        return isinstance(exc, LangSmithNotFoundError)
    except ImportError:
        return False


def _assemble_langsmith_thread_url(project_url: str, thread_id: str) -> str:
    """Format a LangSmith thread URL from a project URL prefix."""
    return f"{project_url.rstrip('/')}/t/{thread_id}?utm_source=opscode"


def get_langsmith_project_name() -> str | None:
    """Resolve the LangSmith project name if tracing is configured."""
    langsmith_key = resolve_env_var("LANGSMITH_API_KEY") or resolve_env_var("LANGCHAIN_API_KEY")
    langsmith_tracing = resolve_env_var("LANGSMITH_TRACING") or resolve_env_var("LANGCHAIN_TRACING_V2")

    if not (langsmith_key and langsmith_tracing):
        return None

    project = (
        resolve_env_var("OPSCODE_LANGSMITH_PROJECT")
        or resolve_env_var("LANGSMITH_PROJECT")
        or resolve_env_var("LANGCHAIN_PROJECT")
        or "opscode"
    )
    return project.strip() or "opscode"


def fetch_langsmith_project_url_or_raise(project_name: str) -> str:
    """Fetch the LangSmith project URL, raising on any failure."""
    global _langsmith_url_cache

    if _langsmith_url_cache is not None:
        cached_name, cached_url = _langsmith_url_cache
        if cached_name == project_name:
            return cached_url

    try:
        from langsmith import Client
    except ImportError as exc:
        logger.debug("langsmith package not installed; cannot fetch project URL for '%s'", project_name)
        raise LangSmithImportError("langsmith package is not installed") from exc

    result: str | None = None
    lookup_error: Exception | None = None
    done = threading.Event()

    def _lookup_url() -> None:
        nonlocal result, lookup_error
        try:
            api_key = resolve_env_var("LANGSMITH_API_KEY") or resolve_env_var("LANGCHAIN_API_KEY")
            project = Client(api_key=api_key).read_project(project_name=project_name)
            result = project.url or None
        except Exception as exc:
            lookup_error = exc
        finally:
            done.set()

    thread = threading.Thread(target=_lookup_url, daemon=True)
    thread.start()

    if not done.wait(_LANGSMITH_URL_LOOKUP_TIMEOUT_SECONDS):
        logger.debug(
            "Timed out fetching LangSmith project URL for '%s' after %.1fs",
            project_name,
            _LANGSMITH_URL_LOOKUP_TIMEOUT_SECONDS,
        )
        raise LangSmithLookupTimeoutError(
            f"LangSmith project URL lookup timed out after {_LANGSMITH_URL_LOOKUP_TIMEOUT_SECONDS:.1f}s"
        )

    if lookup_error is not None:
        logger.debug("Could not fetch LangSmith project URL for '%s'", project_name, exc_info=lookup_error)
        msg = str(lookup_error) or repr(lookup_error)
        if _is_langsmith_not_found(lookup_error):
            raise LangSmithProjectNotFoundError(msg) from lookup_error
        raise LangSmithApiError(msg) from lookup_error

    if not result:
        raise LangSmithApiError(f"LangSmith returned no URL for project '{project_name}'")

    _langsmith_url_cache = (project_name, result)
    return result

def get_cached_langsmith_thread_url(thread_id: str) -> str | None:
    """Build a LangSmith thread URL only when its project URL is cached."""
    project_name = get_langsmith_project_name()
    if not project_name or _langsmith_url_cache is None:
        return None

    cached_name, cached_url = _langsmith_url_cache
    if cached_name != project_name:
        return None
    return _assemble_langsmith_thread_url(cached_url, thread_id)

def build_langsmith_thread_url(thread_id: str) -> str | None:
    """Build a full LangSmith thread URL if tracing is configured."""
    project_name = get_langsmith_project_name()
    if not project_name:
        return None

    try:
        project_url = fetch_langsmith_project_url_or_raise(project_name)
        return _assemble_langsmith_thread_url(project_url, thread_id)
    except Exception:
        return None
