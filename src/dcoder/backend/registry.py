import threading
from typing import Any

class BackendRegistry:
    """Singleton registry for backend providers."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._providers = {}

    def register(self, name: str, cls: type) -> None:
        self._providers[name] = cls

    def build(self, name: str, **kwargs) -> Any:
        cls = self._providers.get(name)
        if cls is None:
            raise ValueError(f"Backend provider '{name}' is not registered.")
        return cls(**kwargs)

    @classmethod
    def get_instance(cls) -> "BackendRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

def get_backend_registry() -> BackendRegistry:
    return BackendRegistry.get_instance()

def register_backend(name: str):
    """Decorator to register a backend provider."""
    def decorator(cls: type):
        get_backend_registry().register(name, cls)
        return cls
    return decorator
