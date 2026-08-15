"""Memory guard middleware for protecting machine-managed onboarding markers."""

from __future__ import annotations

from opscode.memory.guard import ManagedMemoryGuardMiddleware as _ManagedMemoryGuardMiddleware
from opscode.middleware.registry import register_middleware

__all__ = ["ManagedMemoryGuardMiddleware"]


@register_middleware(name="memory_guard")
class ManagedMemoryGuardMiddleware(_ManagedMemoryGuardMiddleware):
    """Protect machine-managed memory regions in AGENTS.md files from being edited."""
