"""Unit tests for Phase 5 Extensibility & Polish modules:
- plugins/
- preferences.py
- welcome.py
"""

from dcoder.plugins import discover_plugins
from dcoder.ui.preferences import UserPreferences, load_preferences
from dcoder.ui.welcome import WelcomeBanner


def test_discover_plugins():
    plugins = discover_plugins()
    assert len(plugins) >= 1
    assert plugins[0].name == "terraform"


from dcoder.ui.theme import get_registry


def test_user_preferences():
    prefs = load_preferences()
    assert isinstance(prefs, UserPreferences)
    assert prefs.theme in get_registry()



def test_welcome_banner_tool_detection():
    banner = WelcomeBanner()
    status = banner._detect_tools()
    assert "terraform" in status
    assert "kubectl" in status
    assert "helm" in status
    assert "ansible" in status
