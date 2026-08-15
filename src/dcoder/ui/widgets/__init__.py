"""Textual widgets for DCoder.

Import directly from submodules, e.g.:

    from dcoder.ui.widgets.chat_input import ChatInput
    from dcoder.ui.widgets.messages import AssistantMessage, MessageList, UserMessage
    from dcoder.ui.widgets.diff import EnhancedDiff, compose_diff_lines
    from dcoder.ui.widgets.autocomplete import AutocompletePopup
    from dcoder.ui.widgets.status import StatusBar
    from dcoder.ui.widgets.subagent_panel import SubagentPanel
    from dcoder.ui.widgets.approval import ApprovalMenu, ApprovalModalScreen
    from dcoder.ui.widgets.ask_user import AskUserMenu
    from dcoder.ui.widgets.goal_review import GoalReviewMenu, GoalReviewScreen
    from dcoder.ui.widgets.model_selector import ModelSelectorScreen
    from dcoder.ui.widgets.theme_selector import ThemeSelectorScreen
    from dcoder.ui.widgets.thread_selector import ThreadSelectorScreen
"""

from __future__ import annotations

from dcoder.ui.widgets.agent_selector import (
    AgentSelectorScreen,
)
from dcoder.ui.widgets.approval import (
    ApprovalDecided,
    ApprovalMenu,
    ApprovalModalScreen,
    assess_tool_risk,
)
from dcoder.ui.widgets.ask_user import (
    AskUserMenu,
    AskUserTextArea,
    OTHER_CHOICE_LABEL,
)
from dcoder.ui.widgets.auth import (
    AuthCheckbox,
    AuthPromptScreen,
    AuthResult,
    CONFIGURATION_DOCS_URL,
    PROVIDER_API_KEY_URLS,
    is_langsmith,
)
from dcoder.ui.widgets.auth_manager import (
    AuthManagerScreen,
)
from dcoder.ui.widgets.auto_mode_notice import (
    AUTO_MODE_DOCS_URL,
    AUTO_MODE_NOTICE_BODY,
    AutoModeNoticeScreen,
)
from dcoder.ui.widgets.autocomplete import (
    AutocompletePopup,
    CompletionController,
    CompletionResult,
    CompletionView,
    FuzzyFileController,
    MultiCompletionManager,
    SlashCommandController,
)
from dcoder.ui.widgets.chat_input import (
    ChatInput,
    ChatTextArea,
    InputMode,
    detect_input_mode,
)
from dcoder.ui.widgets.config_manager import (
    ConfigManagerScreen,
)
from dcoder.ui.widgets.debug_console import (
    DEBUG_TOGGLE_KEY,
    DebugConsoleScreen,
    SnapshotField,
)
from dcoder.ui.widgets.devops_renderers import (
    AnsiblePlaybookRenderer,
    HelmDiffRenderer,
    KubectlRenderer,
    TerraformPlanRenderer,
    TerraformPlanWidget,
)
from dcoder.ui.widgets.diff import (
    EnhancedDiff,
    compose_diff_lines,
)
from dcoder.ui.widgets.effort_selector import (
    EffortSelectorScreen,
)
from dcoder.ui.widgets.goal_review import (
    GoalReviewAccepted,
    GoalReviewCancelled,
    GoalReviewEdited,
    GoalReviewMenu,
    GoalReviewRejected,
    GoalReviewResult,
    GoalReviewScreen,
    GoalReviewTextArea,
)
from dcoder.ui.widgets.goal_status import (
    GoalStatusPanel,
)
from dcoder.ui.widgets.infra_panel import (
    InfraStatePanel,
)
from dcoder.ui.widgets.install_confirm import (
    InstallProviderConfirmScreen,
)
from dcoder.ui.widgets.loading import (
    BRAILLE_SPINNER_FRAMES,
    LoadingWidget,
    Spinner,
    format_duration,
)
from dcoder.ui.widgets.mcp_viewer import (
    MCPServerErrorScreen,
    MCPServerHeaderItem,
    MCPToolItem,
    MCPViewerScreen,
    MCP_VIEWER_RECONNECT_REQUEST,
)
from dcoder.ui.widgets.messages import (
    AppMessage,
    AssistantMessage,
    DiffMessage,
    ErrorMessage,
    FormattedOutput,
    MessageList,
    QueuedUserMessage,
    RubricResultMessage,
    SkillMessage,
    SystemMessage,
    ThinkingMessage,
    ToolCallMessage,
    ToolGroupSummary,
    UserMessage,
    summarize_live_tool_group,
    summarize_tool_group,
)
from dcoder.ui.widgets.model_selector import (
    ModelOption,
    ModelSelectorScreen,
)
from dcoder.ui.widgets.notification_center import (
    NotificationCenter,
)
from dcoder.ui.widgets.notification_settings import (
    NotificationSettingsScreen,
    WARNING_TOGGLES,
)
from dcoder.ui.widgets.operation_card import (
    OperationCard,
)
from dcoder.ui.widgets.permissions_manager import (
    PermissionsManagerScreen,
)
from dcoder.ui.widgets.plugin_manager import (
    PluginManagerScreen,
    PluginTabLabel,
    PluginTabSelected,
)
from dcoder.ui.widgets.preamble import (
    _mode_color,
)
from dcoder.ui.widgets.skills_viewer import (
    SkillDetailScreen,
    SkillItemWidget,
    SkillsViewerScreen,
)
from dcoder.ui.widgets.status import (
    CONNECTION_STATES,
    BranchLabel,
    ConnectionState,
    ModelLabel,
    PROVIDER_PREFIX_STRIPS,
    StatusBar,
)
from dcoder.ui.widgets.subagent_panel import (
    SubagentColumn,
    SubagentPanel,
    SubagentStatus,
    _Phase,
    _SubagentRecord,
    _format_timing,
    sanitize_control_chars,
)
from dcoder.ui.widgets.theme_selector import (
    ThemeSelectorScreen,
)
from dcoder.ui.widgets.thread_selector import (
    CustomOptionList,
    SearchInput,
    ThreadSelector,
    ThreadSelectorScreen,
)
from dcoder.ui.widgets.toast import (
    ToastNotification,
    show_toast,
)
from dcoder.ui.widgets.tool_display import (
    MAX_ARG_LENGTH,
    abbreviate_path,
    format_tool_display,
    format_tool_result_summary,
    get_tool_display_name,
    register_tool_display_name,
    register_tool_summary_formatter,
    truncate_value,
)
from dcoder.ui.widgets.tool_renderers import (
    DeleteFileRenderer,
    EditFileRenderer,
    TaskRenderer,
    ToolRenderer,
    ToolRendererResult,
    WriteFileRenderer,
    get_renderer,
    render_tool_approval,
)
from dcoder.ui.widgets.tool_widgets import (
    EditFileApprovalWidget,
    GenericApprovalWidget,
    TaskApprovalWidget,
    ToolApprovalWidget,
    WriteFileApprovalWidget,
    format_display_content,
)
from dcoder.ui.widgets.welcome import (
    MAX_DISPLAY_ITEMS,
    MAX_INLINE_CHARS,
    WelcomeBanner,
)
from dcoder.ui.widgets.welcome_popup import (
    WelcomeDetailPopup,
)

__all__ = [
    "AUTO_MODE_DOCS_URL",
    "AUTO_MODE_NOTICE_BODY",
    "AgentSelectorScreen",
    "AnsiblePlaybookRenderer",
    "AppMessage",
    "ApprovalDecided",
    "ApprovalMenu",
    "ApprovalModalScreen",
    "AskUserMenu",
    "AskUserTextArea",
    "AssistantMessage",
    "AuthCheckbox",
    "AuthManagerScreen",
    "AuthPromptScreen",
    "AuthResult",
    "AutocompletePopup",
    "AutoModeNoticeScreen",
    "BRAILLE_SPINNER_FRAMES",
    "BranchLabel",
    "CONFIGURATION_DOCS_URL",
    "CONNECTION_STATES",
    "ChatInput",
    "ChatTextArea",
    "CompletionController",
    "CompletionResult",
    "CompletionView",
    "ConfigManagerScreen",
    "ConnectionState",
    "CustomOptionList",
    "DEBUG_TOGGLE_KEY",
    "DebugConsoleScreen",
    "DeleteFileRenderer",
    "DiffMessage",
    "EditFileApprovalWidget",
    "EditFileRenderer",
    "EffortSelectorScreen",
    "EnhancedDiff",
    "ErrorMessage",
    "FormattedOutput",
    "FuzzyFileController",
    "GenericApprovalWidget",
    "GoalReviewAccepted",
    "GoalReviewCancelled",
    "GoalReviewEdited",
    "GoalReviewMenu",
    "GoalReviewRejected",
    "GoalReviewResult",
    "GoalReviewScreen",
    "GoalReviewTextArea",
    "GoalStatusPanel",
    "HelmDiffRenderer",
    "InfraStatePanel",
    "InputMode",
    "InstallProviderConfirmScreen",
    "KubectlRenderer",
    "LoadingWidget",
    "MAX_ARG_LENGTH",
    "MAX_DISPLAY_ITEMS",
    "MAX_INLINE_CHARS",
    "MCPServerErrorScreen",
    "MCPServerHeaderItem",
    "MCPToolItem",
    "MCPViewerScreen",
    "MCP_VIEWER_RECONNECT_REQUEST",
    "MessageList",
    "ModelLabel",
    "ModelOption",
    "ModelSelectorScreen",
    "MultiCompletionManager",
    "NotificationCenter",
    "NotificationSettingsScreen",
    "OTHER_CHOICE_LABEL",
    "OperationCard",
    "PROVIDER_API_KEY_URLS",
    "PROVIDER_PREFIX_STRIPS",
    "PermissionsManagerScreen",
    "PluginManagerScreen",
    "PluginTabLabel",
    "PluginTabSelected",
    "QueuedUserMessage",
    "RubricResultMessage",
    "SearchInput",
    "SkillDetailScreen",
    "SkillItemWidget",
    "SkillMessage",
    "SkillsViewerScreen",
    "SlashCommandController",
    "SnapshotField",
    "Spinner",
    "StatusBar",
    "SubagentColumn",
    "SubagentPanel",
    "SubagentStatus",
    "SystemMessage",
    "TaskApprovalWidget",
    "TaskRenderer",
    "TerraformPlanRenderer",
    "TerraformPlanWidget",
    "ThemeSelectorScreen",
    "ThinkingMessage",
    "ThreadSelector",
    "ThreadSelectorScreen",
    "ToastNotification",
    "ToolApprovalWidget",
    "ToolCallMessage",
    "ToolGroupSummary",
    "ToolRenderer",
    "ToolRendererResult",
    "UserMessage",
    "WARNING_TOGGLES",
    "WelcomeBanner",
    "WelcomeDetailPopup",
    "WriteFileApprovalWidget",
    "WriteFileRenderer",
    "_Phase",
    "_SubagentRecord",
    "_format_timing",
    "_mode_color",
    "abbreviate_path",
    "assess_tool_risk",
    "compose_diff_lines",
    "detect_input_mode",
    "format_display_content",
    "format_duration",
    "format_tool_display",
    "format_tool_result_summary",
    "get_renderer",
    "get_tool_display_name",
    "is_langsmith",
    "register_tool_display_name",
    "register_tool_summary_formatter",
    "render_tool_approval",
    "sanitize_control_chars",
    "show_toast",
    "summarize_live_tool_group",
    "summarize_tool_group",
    "truncate_value",
]
