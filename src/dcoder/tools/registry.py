"""Dynamic tool registry to register and instantiate dcoder tools."""

import threading
from typing import Callable
from langchain_core.tools import BaseTool

class ToolRegistry:
    """Registry to bind and configure tools dynamically."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._registry: dict[str, Callable[..., BaseTool]] = {}

    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, name: str, factory: Callable[..., BaseTool]) -> None:
        """Register a tool factory function."""
        self._registry[name] = factory

    def build_tool(self, name: str, **kwargs) -> BaseTool:
        """Build and configure a registered tool."""
        if name not in self._registry:
            raise KeyError(f"Tool '{name}' is not registered in ToolRegistry.")
        return self._registry[name](**kwargs)

    def build_all(self, names: list[str], **kwargs) -> list[BaseTool]:
        """Build a list of tools by name."""
        tools = []
        for name in names:
            try:
                tools.append(self.build_tool(name, **kwargs))
            except KeyError:
                # Log or warn if needed, or skip
                pass
        return tools
