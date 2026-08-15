"""OpsCode backend modules."""

from opscode.backend.registry import (
    BackendRegistry,
    register_backend,
    get_backend_registry,
)
from opscode.backend.local import LocalShellBackend
from opscode.backend.composite import DCodCompositeBackend

__all__ = [
    "BackendRegistry",
    "register_backend",
    "get_backend_registry",
    "LocalShellBackend",
    "DCodCompositeBackend",
]
