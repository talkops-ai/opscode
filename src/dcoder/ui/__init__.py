"""DCoder TUI widgets package.

Exports the public widget classes that ``DCoderApp`` and the
``TextualAdapter`` compose the interface from.
"""

from dcoder.ui.app import DCoderApp
from dcoder.ui.approval import (
    ApprovalDecided,
    ApprovalMenu,
    ApprovalModalScreen,
    assess_tool_risk,
)
from dcoder.ui.ask_user import AskUserMenu
from dcoder.ui.chat_input import ChatInput
from dcoder.ui.devops_renderers import TerraformPlanWidget
from dcoder.ui.diff import compose_diff_lines
from dcoder.ui.infra_panel import InfraStatePanel
from dcoder.ui.messages import (
    AssistantMessage,
    DiffMessage,
    ErrorMessage,
    MessageList,
    QueuedUserMessage,
    SkillMessage,
    SystemMessage,
    ToolCallMessage,
    ToolGroupSummary,
    UserMessage,
)
from dcoder.ui.notification_center import NotificationCenter
from dcoder.ui.operation_card import OperationCard
from dcoder.ui.plugin_manager import PluginManagerScreen
from dcoder.ui.preferences import ThemeSelector
from dcoder.ui.skills_viewer import SkillsViewerScreen


from dcoder.ui.status import StatusBar
from dcoder.ui.subagent_panel import SubagentColumn, SubagentPanel
from dcoder.ui.textual_adapter import TextualAdapter
from dcoder.ui.toast import ToastNotification, show_toast
from dcoder.ui.ui_help import (
    show_agents_help,
    show_auth_help,
    show_config_help,
    show_doctor_help,
    show_help,
    show_list_help,
    show_mcp_config_help,
    show_mcp_help,
    show_mcp_login_help,
    show_plugins_help,
    show_reset_help,
    show_skills_help,
    show_skills_info_help,
    show_skills_list_help,
    show_skills_trust_help,
    show_threads_delete_help,
    show_threads_help,
    show_threads_list_help,
    show_tools_help,
    show_tools_install_help,
    show_tools_list_help,
)
from dcoder.ui.welcome import WelcomeBanner
from dcoder.ui.welcome_popup import WelcomeDetailPopup

__all__ = [
    "ApprovalDecided",
    "ApprovalMenu",
    "ApprovalModalScreen",
    "AskUserMenu",
    "AssistantMessage",
    "ChatInput",
    "DCoderApp",
    "DiffMessage",
    "ErrorMessage",
    "InfraStatePanel",
    "MessageList",
    "NotificationCenter",
    "OperationCard",
    "QueuedUserMessage",
    "SkillMessage",
    "StatusBar",
    "SubagentColumn",
    "SubagentPanel",
    "SystemMessage",
    "TerraformPlanWidget",
    "TextualAdapter",
    "ThemeSelector",
    "ToastNotification",
    "ToolCallMessage",
    "ToolGroupSummary",
    "UserMessage",
    "WelcomeBanner",
    "WelcomeDetailPopup",
    "assess_tool_risk",
    "compose_diff_lines",
    "show_agents_help",
    "show_auth_help",
    "show_config_help",
    "show_doctor_help",
    "show_help",
    "show_list_help",
    "show_mcp_config_help",
    "show_mcp_help",
    "show_mcp_login_help",
    "show_plugins_help",
    "show_reset_help",
    "show_skills_help",
    "show_skills_info_help",
    "show_skills_list_help",
    "show_skills_trust_help",
    "show_threads_delete_help",
    "show_threads_help",
    "show_threads_list_help",
    "show_toast",
    "show_tools_help",
    "show_tools_install_help",
    "show_tools_list_help",
]


