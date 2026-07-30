"""Composite backend routing for dcoder."""

import tempfile
from typing import Any

from deepagents.backends import CompositeBackend, FilesystemBackend, BackendProtocol

class DCodCompositeBackend(CompositeBackend):
    """Composite backend for routing special paths to temp/virtual backends."""

    def __init__(self, default: Any, routes: dict[str, Any] | None = None, **kwargs: Any):
        import atexit

        self._large_results_dir = tempfile.mkdtemp(prefix="dcoder_large_results_")
        self._conversation_history_dir = tempfile.mkdtemp(prefix="dcoder_conversation_history_")

        atexit.register(self.cleanup)

        large_results_backend = FilesystemBackend(
            root_dir=self._large_results_dir,
            virtual_mode=True,
        )
        conversation_history_backend = FilesystemBackend(
            root_dir=self._conversation_history_dir,
            virtual_mode=True,
        )

        effective_routes: dict[str, BackendProtocol] = {
            "/large_tool_results/": large_results_backend,
            "/conversation_history/": conversation_history_backend,
        }
        if routes:
            effective_routes.update(routes)

        super().__init__(
            default=default,
            routes=effective_routes,
            **kwargs,
        )

    def cleanup(self) -> None:
        """Explicitly clean up temporary directories."""
        import shutil
        if hasattr(self, "_large_results_dir") and self._large_results_dir:
            shutil.rmtree(self._large_results_dir, ignore_errors=True)
        if hasattr(self, "_conversation_history_dir") and self._conversation_history_dir:
            shutil.rmtree(self._conversation_history_dir, ignore_errors=True)

    def __enter__(self) -> "DCodCompositeBackend":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup()
