import threading
from typing import Any, Callable, Dict, Set, Type, TypeVar
from langchain.agents.middleware.types import AgentMiddleware

class MiddlewareRegistry:
    """Registry of middleware. Preserves insertion order."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._registry: Dict[str, tuple[Type[AgentMiddleware], Dict[str, Any]]] = {}

    def register(
        self,
        name: str,
        cls: Type[AgentMiddleware],
        *,
        default_kwargs: Dict[str, Any] | None = None,
    ) -> None:
        self._registry[name] = (cls, default_kwargs or {})

    def build_stack(self, *, exclude: Set[str] | None = None, **kwargs: Any) -> list[AgentMiddleware]:
        # Insertion order preserved
        items = [
            (name, item) for name, item in self._registry.items() if not (exclude and name in exclude)
        ]
        stack = []
        for name, (cls, default_kwargs) in items:
            inst_kwargs = {**default_kwargs, **kwargs.get(name, {})}
            stack.append(cls(**inst_kwargs))
        return stack

    @classmethod
    def get_instance(cls) -> "MiddlewareRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance


def get_middleware_registry() -> MiddlewareRegistry:
    return MiddlewareRegistry.get_instance()


T = TypeVar("T", bound=type)

def register_middleware(
    name: str,
    *,
    default_kwargs: Dict[str, Any] | None = None,
) -> Callable[[T], T]:
    """Decorator to register a middleware class."""
    def decorator(cls: T) -> T:
        get_middleware_registry().register(name, cls, default_kwargs=default_kwargs)
        return cls
    return decorator

