import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from dcoder.backend.registry import BackendRegistry, register_backend
from dcoder.backend.local import _build_shell_env, LocalShellBackend
from dcoder.backend.composite import DCodCompositeBackend

def test_backend_registry():
    registry = BackendRegistry()
    
    class MockBackend:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            
    registry.register("mock", MockBackend)
    inst = registry.build("mock", foo="bar")
    assert isinstance(inst, MockBackend)
    assert inst.kwargs == {"foo": "bar"}


def test_register_backend_decorator():
    from dcoder.backend.registry import get_backend_registry
    global_registry = get_backend_registry()
    
    @register_backend("decorator_mock")
    class DecoratorMockBackend:
        pass
        
    assert "decorator_mock" in global_registry._providers
    # Clean up global registry to prevent pollution
    global_registry._providers.pop("decorator_mock", None)


def test_build_shell_env():
    with patch.dict(os.environ, {"KUBECONFIG": "/fake/kubeconfig", "AWS_PROFILE": "devops", "SECRET_KEY": "leak"}):
        env = _build_shell_env()
        assert env.get("KUBECONFIG") == "/fake/kubeconfig"
        assert env.get("AWS_PROFILE") == "devops"
        assert "SECRET_KEY" not in env  # Curated env should filter out non-safe, non-DevOps keys


def test_composite_routing():
    mock_default = MagicMock()
    comp = DCodCompositeBackend(default=mock_default)
    assert "/large_tool_results/" in comp.routes
    assert "/conversation_history/" in comp.routes
