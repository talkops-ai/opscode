import atexit
import os
import shutil
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from opscode.config.settings import _load_dotenv
from opscode.config.manifest import DOTENV_DENIED_ENV_KEYS
from opscode.backend.registry import BackendRegistry
from opscode.middleware.registry import MiddlewareRegistry
from opscode.backend.composite import DCodCompositeBackend

def test_registry_thread_safety():
    """Verify that BackendRegistry and MiddlewareRegistry instances are thread-safe singletons."""
    backend_instances = []
    middleware_instances = []
    
    def get_backend():
        backend_instances.append(BackendRegistry.get_instance())
        
    def get_middleware():
        middleware_instances.append(MiddlewareRegistry.get_instance())
        
    threads = []
    for _ in range(10):
        t1 = threading.Thread(target=get_backend)
        t2 = threading.Thread(target=get_middleware)
        threads.extend([t1, t2])
        t1.start()
        t2.start()
        
    for t in threads:
        t.join()
        
    # All threads should have received the exact same singleton instance
    assert len(set(id(inst) for inst in backend_instances)) == 1
    assert len(set(id(inst) for inst in middleware_instances)) == 1


def test_dotenv_precedence(tmp_path, monkeypatch):
    """Verify that project-level dotenv variables overwrite global dotenv values (higher precedence)."""
    # Create temp global and project directories
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    
    global_env = global_dir / ".env"
    global_env.write_text("TEST_PRECEDENCE=global_value\nGLOBAL_ONLY=global_only")
    
    project_env = project_dir / ".env"
    project_env.write_text("TEST_PRECEDENCE=project_value\nPROJECT_ONLY=project_only")
    
    # Mock paths.GLOBAL_ENV_PATH to point to our temp global .env
    import opscode.config.paths as paths_mod
    monkeypatch.setattr(paths_mod, "GLOBAL_ENV_PATH", global_dir / ".env")
    
    # Run _load_dotenv starting from project directory
    # Clear env keys first to ensure a clean test state
    monkeypatch.delenv("TEST_PRECEDENCE", raising=False)
    monkeypatch.delenv("GLOBAL_ONLY", raising=False)
    monkeypatch.delenv("PROJECT_ONLY", raising=False)
    
    _load_dotenv(start_path=project_dir, refresh_loaded=True)
    
    assert os.environ.get("GLOBAL_ONLY") == "global_only"
    assert os.environ.get("PROJECT_ONLY") == "project_only"
    # Project value should take precedence and overwrite global
    assert os.environ.get("TEST_PRECEDENCE") == "project_value"


def test_composite_backend_cleanup(monkeypatch):
    """Verify that temporary directories created by DCodCompositeBackend are registered for exit cleanup."""
    registered_callbacks = []
    
    def mock_register(func, *args, **kwargs):
        registered_callbacks.append(func)
        
    monkeypatch.setattr(atexit, "register", mock_register)
    
    mock_default = MagicMock()
    backend = DCodCompositeBackend(default=mock_default)
    
    # Assert that a cleanup function was registered with atexit
    assert len(registered_callbacks) == 1
    cleanup_func = registered_callbacks[0]
    assert cleanup_func.__name__ == "cleanup"
