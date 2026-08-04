import pytest
from dcoder.middleware.local_context import build_detect_script, LocalContextMiddleware

def test_build_detect_script():
    script = build_detect_script()
    assert "git status" in script or "git --version" in script
    assert "node -v" in script or "node" in script
