"""Unit tests for Phase 5 Extensibility & Polish modules:
- plugins/
- preferences.py
- welcome.py
"""

from dcoder.plugins import discover_plugins
from dcoder.ui.preferences import UserPreferences, load_preferences
from dcoder.ui.widgets.welcome import WelcomeBanner


def test_discover_plugins():
    plugins = discover_plugins()
    assert len(plugins) >= 1
    assert plugins[0].name == "terraform"


from dcoder.ui.theme import get_registry


def test_user_preferences():
    prefs = load_preferences()
    assert isinstance(prefs, UserPreferences)
    assert prefs.theme in get_registry()



def test_devops_tool_detection():
    from dcoder.commands.core.doctor import DoctorHandler

    handler = DoctorHandler()
    sec = handler._collect_devops_tools()
    tool_labels = [i.label.lower() for i in sec.items]
    assert "terraform" in tool_labels
    assert "kubectl" in tool_labels
    assert "helm" in tool_labels
    assert "docker" in tool_labels
