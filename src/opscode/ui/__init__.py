"""OpsCode TUI package.

Exports core application and adapter classes, as well as re-exports of primary
UI widgets from ``opscode.ui.widgets``.
"""

from opscode.ui.app import OpsCodeApp
from opscode.ui.textual_adapter import TextualAdapter
from opscode.ui.preferences import ThemeSelector
from opscode.ui.ui_help import (
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
from opscode.ui.widgets.approval import (
    ApprovalDecided,
    ApprovalMenu,
    ApprovalModalScreen,
    assess_tool_risk,
)
from opscode.ui.widgets.ask_user import AskUserMenu
from opscode.ui.widgets.chat_input import ChatInput
from opscode.ui.widgets.devops_renderers import TerraformPlanWidget
from opscode.ui.widgets.diff import compose_diff_lines
from opscode.ui.widgets.infra_panel import InfraStatePanel
from opscode.ui.widgets.messages import (
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
from opscode.ui.widgets.notification_center import NotificationCenter
from opscode.ui.widgets.operation_card import OperationCard
from opscode.ui.widgets.plugin_manager import PluginManagerScreen
from opscode.ui.widgets.skills_viewer import SkillsViewerScreen
from opscode.ui.widgets.status import StatusBar
from opscode.ui.widgets.subagent_panel import SubagentColumn, SubagentPanel
from opscode.ui.widgets.toast import ToastNotification, show_toast
from opscode.ui.widgets.welcome import WelcomeBanner
from opscode.ui.widgets.welcome_popup import WelcomeDetailPopup

__all__ = [
    "ApprovalDecided",
    "ApprovalMenu",
    "ApprovalModalScreen",
    "AskUserMenu",
    "AssistantMessage",
    "ChatInput",
    "OpsCodeApp",
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
