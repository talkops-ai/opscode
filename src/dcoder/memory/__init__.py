"""Persistent memory and onboarding wizard for dcoder."""

from dcoder.memory.registry import MemoryRegistry
from dcoder.memory.guard import ManagedMemoryGuardMiddleware
from dcoder.memory.onboarding import run_onboarding_if_needed

__all__ = [
    "MemoryRegistry",
    "ManagedMemoryGuardMiddleware",
    "run_onboarding_if_needed",
]
