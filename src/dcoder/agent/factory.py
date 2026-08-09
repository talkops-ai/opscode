from __future__ import annotations
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence, TYPE_CHECKING, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.pregel import Pregel

if TYPE_CHECKING:
    from dcoder.backend.composite import DCodCompositeBackend

logger = logging.getLogger("dcoder")


def _sanitize_agent_message_name(raw: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", raw)
    return cleaned if cleaned else "agent"



@dataclass
class CLIContextSchema:
    model: str | None = None
    model_params: dict[str, Any] = field(default_factory=dict)
    profile_overrides: dict[str, Any] = field(default_factory=dict)
    model_context_limit: int | None = None
    approval_mode: str = "manual"
    auto_approve: bool = False
    approval_mode_key: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    offload_tool_call_id: str | None = None
    hooks_snapshot_id: str | None = None
    hooks_server_events: list[str] = field(default_factory=list)
    prompt_id: str | None = None


def run_sync(coro):
    import asyncio
    try:
        return asyncio.run(coro)
    except RuntimeError:
        from concurrent.futures import ThreadPoolExecutor
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(asyncio.run, coro).result()
        except BaseException as exc:
            logger.warning("run_sync thread execution failed: %s", exc)
            return []
    except BaseException as exc:
        logger.warning("run_sync execution failed: %s", exc)
        return []


from langchain.agents.middleware.types import AgentMiddleware


def _should_interrupt_tool_call(request: Any, *, auto_mode_enabled: bool = True) -> bool:
    """Decide whether a gated tool call should pause for human approval."""
    from dcoder.middleware.auto_mode import _async_routing_mode
    from dcoder.security.approval_mode import ApprovalMode, coerce_approval_mode, read_approval_mode_from_store, approval_mode_key

    # 1. Check async routing mode attached by AsyncApprovalHITLMiddleware / AutoModeHITLMiddleware
    mode = _async_routing_mode(getattr(request, "state", None))
    runtime = getattr(request, "runtime", None)

    # 2. Fall back to context / store resolution if no async routing decision present
    if mode is None and runtime is not None:
        ctx = getattr(runtime, "context", None)
        store = getattr(runtime, "store", None)
        if isinstance(ctx, dict):
            if ctx.get("auto_approve"):
                mode = ApprovalMode.YOLO
            elif ctx.get("approval_mode"):
                mode = coerce_approval_mode(ctx.get("approval_mode"))
            elif ctx.get("thread_id"):
                key = approval_mode_key(str(ctx["thread_id"]))
                mode = read_approval_mode_from_store(store, key)
        elif ctx is not None:
            if getattr(ctx, "auto_approve", False):
                mode = ApprovalMode.YOLO

    if mode is ApprovalMode.YOLO:
        return False
    if mode is ApprovalMode.AUTO:
        return not auto_mode_enabled

    # Never interrupt internal memory file writes (e.g. AGENTS.md)
    tool_call = getattr(request, "action", None) or getattr(request, "tool_call", None)
    if isinstance(tool_call, dict):
        args = tool_call.get("args") or {}
        path_str = str(args.get("path") or args.get("TargetFile") or "")
        if "AGENTS.md" in path_str:
            return False

    return True


def _format_task_description(tool_call: Any, state: Any = None, runtime: Any = None) -> str:
    """Format task (subagent) tool call for approval prompt."""
    args = tool_call.get("args") or {} if isinstance(tool_call, dict) else getattr(tool_call, "args", {}) or {}
    description = str(args.get("description") or "unknown")
    subagent_type = str(args.get("subagent_type") or args.get("name") or "unknown")

    description_preview = description
    if len(description) > 500:
        description_preview = description[:500] + "..."

    separator = "━" * 40
    warning_msg = "Subagent will have access to file operations and shell commands"
    return (
        f"Subagent Type: {subagent_type}\n\n"
        f"⚠️ {warning_msg} ⚠️\n\n"
        f"Task Instructions:\n"
        f"{separator}\n"
        f"{description_preview}"
    )


def _format_description(tool_call: Any, state: Any = None, runtime: Any = None) -> str:
    name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
    args = tool_call.get("args") or {} if isinstance(tool_call, dict) else getattr(tool_call, "args", {}) or {}
    if name == "execute":
        command = args.get("command", "")
        if "destroy" in command:
            return f"⚠️ DESTRUCTIVE: Running terraform destroy — will delete infrastructure"
        if "delete" in command:
            return f"⚠️ DESTRUCTIVE: Running kubectl/cli delete — will delete resources"
        if "apply" in command:
            return f"Running terraform/kubectl apply — will create/modify infrastructure"
        return f"Shell command execution: {command}"
    elif name == "write_file":
        return f"Write to file: {args.get('path') or args.get('TargetFile')}"
    elif name == "edit_file":
        return f"Edit file: {args.get('path') or args.get('TargetFile')}"
    elif name == "delete":
        return f"⚠️ DESTRUCTIVE: Delete file: {args.get('path') or args.get('TargetFile')}"
    elif name == "web_search":
        return f"Perform web search: {args.get('query')}"
    elif name == "fetch_url":
        return f"Fetch external URL content: {args.get('url') or args.get('Url')}"
    elif name == "task":
        return _format_task_description(tool_call, state, runtime)
    elif name in ("start_async_task", "update_async_task", "cancel_async_task"):
        return f"Launch, update, or cancel a remote async subagent: {args.get('name') or args.get('task_id') or ''}"
    elif name == "compact_conversation":
        return f"Compact conversation history"
    return f"Execute tool '{name}' with arguments: {args}"


def _get_harness_tool_descriptions(
    model: str | BaseChatModel,
) -> dict[str, str]:
    """Return the SDK harness's tool-description overrides for `model`."""
    try:
        from deepagents.profiles.harness.harness_profiles import (
            _get_harness_profile,
            _harness_profile_for_model,
        )

        if isinstance(model, str):
            profile = _get_harness_profile(model)
            return dict(profile.tool_description_overrides) if profile is not None else {}
        return dict(_harness_profile_for_model(model, None).tool_description_overrides)
    except Exception as exc:
        logger.debug("Harness profile lookup skipped: %s", exc)
        return {}


def _subagent_cli_middleware(
    *,
    has_explicit_model: bool,
    assistant_id: str,
    subagent_name: str,
    allowed_tools: Sequence[str] | None = None,
    allowed_skills: Sequence[str] | None = None,
    interactive: bool = True,
    shell_allow_list: list[str] | None = None,
    interrupt_on: dict[str, Any] | None = None,
    worktree_root: str | Path | None = None,
) -> list[Any]:
    from deepagents.backends import FilesystemBackend
    from dcoder.middleware.configurable_model import ConfigurableModelMiddleware
    from dcoder.middleware.tool_filter import ToolFilterMiddleware
    from dcoder.middleware.skills import PluginSkillsMiddleware
    from dcoder.memory.guard import ManagedMemoryGuardMiddleware
    from dcoder.memory.branch import BranchMemoryStore
    from dcoder.skills import SkillRegistry
    from dcoder.config.settings import settings

    middleware: list[AgentMiddleware[Any, Any]] = []
    if interrupt_on is not None:
        from dcoder.middleware.auto_mode import AsyncApprovalHITLMiddleware
        middleware.append(AsyncApprovalHITLMiddleware(interrupt_on))

    if not has_explicit_model:
        middleware.append(ConfigurableModelMiddleware(persist_model_state=False))

    from dcoder.middleware.cost_tracking import CostTrackingMiddleware
    middleware.append(CostTrackingMiddleware(nested=True))

    if not interactive:
        from dcoder.middleware.glm_stall_recovery import GlmTerminalStallRecoveryMiddleware
        middleware.append(GlmTerminalStallRecoveryMiddleware())

    if shell_allow_list:
        from dcoder.middleware.shell_allow_list import ShellAllowListMiddleware
        middleware.append(ShellAllowListMiddleware(shell_allow_list))

    from dcoder.middleware.server_hooks import ServerHooksMiddleware
    subagent_cwd = Path(worktree_root) if worktree_root is not None else Path.cwd()
    middleware.append(
        ServerHooksMiddleware(
            cwd=subagent_cwd,
            emit_stop=False,
        )
    )

    # Tool Filtering Proxy Middleware
    if allowed_tools:
        middleware.append(ToolFilterMiddleware(allowed_patterns=allowed_tools))

    # Scoped Skill Middleware for Subagent
    skill_sources = SkillRegistry.get_instance().get_sources_for_middleware()
    if skill_sources:
        middleware.append(
            PluginSkillsMiddleware(
                backend=FilesystemBackend(virtual_mode=False),
                sources=skill_sources,
                allowed_skills=allowed_skills,
            )
        )

    # Branch Memory Store for subagent execution isolation
    branch_store = BranchMemoryStore(subagent_name=subagent_name)
    memory_sources = [
        str(branch_store.branch_file),
        str(settings.get_user_agent_md_path(assistant_id)),
    ]
    middleware.append(ManagedMemoryGuardMiddleware(memory_sources))
    return middleware


INTERPRETER_PTC_SAFE_PRESET: frozenset[str] = frozenset({"read_file", "glob", "grep"})
_INTERPRETER_WRITE_TOOLS: frozenset[str] = frozenset(
    {
        "execute",
        "write_file",
        "edit_file",
        "delete",
        "replace_file_content",
        "multi_replace_file_content",
        "write_to_file",
        "write_todos",
        "task",
        "start_async_task",
        "update_async_task",
        "cancel_async_task",
    }
)

def _resolve_ptc_option(
    ptc: str | bool | list[str] | None,
    *,
    tools: Sequence[BaseTool | Callable | dict[str, Any]],
    acknowledge_unsafe: bool,
    auto_approve: bool,
) -> list[str] | None:
    from langchain.tools import BaseTool as _BaseTool

    if ptc is False or ptc is None or ptc == []:
        return None

    live_names: list[str] = []
    for candidate in tools:
        if isinstance(candidate, _BaseTool):
            name = candidate.name
            if isinstance(name, str):
                live_names.append(name)
        elif isinstance(candidate, dict):
            raw_name = cast("dict[str, Any]", candidate).get("name")
            if isinstance(raw_name, str):
                live_names.append(raw_name)
        else:
            attr = getattr(candidate, "name", None)
            if isinstance(attr, str):
                live_names.append(attr)
    live_set: set[str] = set(live_names)

    if isinstance(ptc, str):
        normalized = ptc.strip().lower()
        if normalized == "safe":
            return sorted(INTERPRETER_PTC_SAFE_PRESET)
        if normalized == "all":
            if not auto_approve and not acknowledge_unsafe:
                msg = (
                    "interpreter_ptc='all' exposes every host tool to PTC "
                    "calls that bypass HITL approval. Set "
                    "interpreter_ptc_acknowledge_unsafe=True (or use "
                    "auto_approve=True) to opt in."
                )
                raise ValueError(msg)
            included = sorted(live_set)
            write_included = sorted(_INTERPRETER_WRITE_TOOLS & live_set)
            if write_included:
                logger.info(
                    "interpreter_ptc='all' includes write/shell tools: %s",
                    write_included,
                )
            return included
        msg = (
            f"Invalid interpreter_ptc preset {ptc!r}. "
            "Must be 'safe', 'all', or a list of tool names."
        )
        raise ValueError(msg)

    if isinstance(ptc, list):
        if "all" in ptc:
            msg = "interpreter_ptc cannot contain 'all' within a list."
            raise ValueError(msg)
        resolved: set[str] = set()
        for item in ptc:
            if not isinstance(item, str):
                raise ValueError(f"Invalid interpreter_ptc item {item!r}; expected string.")
            normalized = item.strip().lower()
            if normalized == "safe":
                for member in sorted(INTERPRETER_PTC_SAFE_PRESET):
                    resolved.add(member)
            else:
                resolved.add(item)
        included = sorted(resolved)
        write_included = sorted(_INTERPRETER_WRITE_TOOLS & resolved)
        if write_included and not auto_approve and not acknowledge_unsafe:
            msg = (
                f"interpreter_ptc includes write/shell tools {write_included} "
                "that bypass HITL approval. Set "
                "interpreter_ptc_acknowledge_unsafe=True (or use auto_approve=True) "
                "to opt in."
            )
            raise ValueError(msg)
        return included

    raise ValueError(f"Invalid interpreter_ptc type: {type(ptc)}")


def create_dcoder_agent(
    model: str | BaseChatModel,
    *,
    assistant_id: str = "dcoder",
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    mcp_tools: Sequence[BaseTool] | None = None,
    system_prompt: str | None = None,
    interactive: bool = True,
    auto_approve: bool = False,
    enable_shell: bool = True,
    enable_interpreter: bool = True,
    enable_ask_user: bool = True,
    fs_tools: list[str] | None = None,
    async_subagents: Sequence[Any] | None = None,
    checkpointer: Any | None = None,
    cwd: str | Path | None = None,
    sandbox: str | None = None,
    thread_id: str | None = None,
    goal_criteria_tools: Sequence[BaseTool | Callable[..., Any]] | None = None,
) -> tuple[Pregel[Any, Any, Any, Any], DCodCompositeBackend]:
    """Create a compiled dcoder agent graph.
    
    1. Resolves settings and agent directories.
    2. Builds local backend or remote sandbox backend and routing.
    3. Builds middleware stack with security allow-lists and resume channels.
    4. Generates DevOps-specific system prompt with injected MCP inventory.
    5. Configures human-in-the-loop gates.
    6. Compiles agent graph with SQLite checkpointer.
    """
    # Lazy imports to prevent premature settings bootstrapping
    from deepagents import create_deep_agent
    from deepagents.backends import FilesystemBackend
    from langchain.agents.middleware import InterruptOnConfig
    from dcoder.config.settings import settings
    from dcoder.model.factory import create_model
    from dcoder.backend.local import LocalShellBackend
    from dcoder.backend.composite import DCodCompositeBackend
    from dcoder.middleware.registry import get_middleware_registry
    from dcoder.prompts import get_base_system_prompt
    from dcoder.tools.registry import ToolRegistry
    from dcoder.tools.catalog import register_all_tools

    # 1. Resolve working directory and execution environment
    effective_cwd: Path
    if cwd is not None:
        effective_cwd = Path(cwd)
    elif settings.project_root is not None:
        effective_cwd = settings.project_root
    else:
        effective_cwd = Path(os.environ.get("PWD", "."))

    # 2. Create backend FIRST so it can be passed to tools
    if sandbox:
        from dcoder.backend.sandbox.factory import create_sandbox
        t_id = thread_id or assistant_id
        backend = create_sandbox(sandbox, thread_id=t_id)
    elif enable_shell:
        backend = LocalShellBackend(root_dir=effective_cwd)
    else:
        backend = FilesystemBackend(root_dir=effective_cwd, virtual_mode=False)

    # Wrap in composite backend for virtual path routing
    composite_backend = DCodCompositeBackend(default=backend)

    # 3. Register all tools and build tool list
    register_all_tools()
    registry = ToolRegistry.get_instance()
    tools_list = list(tools) if tools is not None else []
    
    # Append default tools if not already present
    default_tool_names = [
        "web_search", "fetch_url",
        "terraform_validate", "terraform_plan", "terraform_fmt",
        "helm_lint", "helm_template",
        "kubectl_get", "kubectl_describe", "kubectl_logs",
        "ansible_check", "argocd_diff"
    ]
    for tool_name in default_tool_names:
        if not any(getattr(t, "name", None) == tool_name for t in tools_list):
            try:
                tools_list.append(registry.build_tool(tool_name, backend=composite_backend))
            except Exception as e:
                logger.warning("Failed to build registered tool %s: %s", tool_name, e)

    # Discovered MCP Configs
    mcp_tools_list: list[Any] = list(mcp_tools) if mcp_tools is not None else []
    mcp_manager = None
    mcp_config = None

    if mcp_tools is None:
        from dcoder.mcp.discovery import MCPDiscovery
        from dcoder.mcp.session_manager import MCPSessionManager
        from dcoder.mcp.trust import is_project_mcp_trusted, compute_config_fingerprint

        discovery = MCPDiscovery()
        mcp_config = discovery.discover()
        
        project_config_path = settings.project_root / ".mcp.json" if settings.project_root else None
        trust_project = True
        if project_config_path and project_config_path.exists():
            fingerprint = compute_config_fingerprint([project_config_path])
            trust_project = is_project_mcp_trusted(str(settings.project_root), fingerprint)
            if not trust_project:
                logger.warning("Project MCP configuration is untrusted. Skipping project-level MCP tools.")
        
        mcp_manager = MCPSessionManager(mcp_config)
        if mcp_config:
            try:
                connected = run_sync(mcp_manager.connect_all(trust_project=trust_project))
                mcp_tools_list = list(connected) if connected else []
            except BaseException as e:
                logger.warning("Failed to connect to MCP servers: %s", e)
                mcp_tools_list = []

    tools_list.extend(mcp_tools_list)

    # 4. Ensure dcoder agent directory exists
    settings.ensure_agent_dir(assistant_id)

    # 5. Resolve model if it was passed as string spec
    if isinstance(model, str):
        model_res = create_model(model)
        model_res.apply_to_settings()
        active_model = model_res.model
    else:
        active_model = model

    # 6. Build ordered middleware stack
    from dcoder.middleware import (
        ConfigurableModelMiddleware,
        ResumeStateMiddleware,
        GoalToolsMiddleware,
        LocalContextMiddleware,
        PluginSkillsMiddleware,
        CLICompactionMiddleware,
        _create_cli_compaction_middleware,
        ManagedMemoryGuardMiddleware,
        ReliableRubricMiddleware,
    )
    from deepagents.middleware import MemoryMiddleware

    # Generate or use custom system prompt
    # Generate or use custom system prompt
    if system_prompt is None:
        from deepagents._models import get_model_provider
        from dcoder.config.settings import settings
        
        model_name = getattr(active_model, "model_name", None) or getattr(active_model, "model", None)
        provider = get_model_provider(active_model)
        
        base_prompt = get_base_system_prompt(
            assistant_id=assistant_id,
            interactive=interactive,
            cwd=effective_cwd,
            fs_tools=fs_tools,
            model_name=model_name if isinstance(model_name, str) else None,
            model_provider=provider,
            model_context_limit=settings.model_context_limit,
        )
    else:
        base_prompt = system_prompt

    agent_middleware: list[AgentMiddleware[Any, Any]] = [
        ConfigurableModelMiddleware(),
    ]

    # Non-interactive / Headless Guard Middlewares (Early)
    if not interactive:
        from dcoder.middleware.glm_stall_recovery import GlmTerminalStallRecoveryMiddleware
        agent_middleware.append(GlmTerminalStallRecoveryMiddleware())
        
        if mcp_tools_list:
            from dcoder.middleware.headless_mcp_guard import HeadlessMCPGuardMiddleware, gated_mcp_tool_names
            if gated_names := gated_mcp_tool_names(mcp_tools_list):
                agent_middleware.append(HeadlessMCPGuardMiddleware(gated_names))

    from dcoder.middleware.cost_tracking import CostTrackingMiddleware
    agent_middleware.extend(
        [ResumeStateMiddleware(), CostTrackingMiddleware(), GoalToolsMiddleware()]
    )

    # AskUser Middleware (if enabled)
    if enable_ask_user:
        from dcoder.middleware.ask_user import AskUserMiddleware
        agent_middleware.append(AskUserMiddleware())

    # Memory Middleware & Guard
    from dcoder.memory import MemoryRegistry
    memory_sources = MemoryRegistry.get_instance().get_all_memory_sources(assistant_id)
    memory_sources_str = [str(s) for s in memory_sources]
    if memory_sources_str:
        agent_middleware.append(
            MemoryMiddleware(
                backend=FilesystemBackend(virtual_mode=False),
                sources=memory_sources_str,
            )
        )
        agent_middleware.append(
            ManagedMemoryGuardMiddleware(guarded_paths=memory_sources_str)
        )

    # Plugin Skills Middleware
    from dcoder.skills import SkillRegistry
    SkillRegistry.get_instance().discover_skills()
    skill_sources = SkillRegistry.get_instance().get_sources_for_middleware()
    if skill_sources:
        agent_middleware.append(
            PluginSkillsMiddleware(
                backend=FilesystemBackend(virtual_mode=False),
                sources=skill_sources,
            )
        )

    # CodeInterpreter Middleware (if enabled)
    if enable_interpreter:
        if sandbox is not None:
            raise ValueError("enable_interpreter=True is not supported with a remote sandbox.")
        try:
            from langchain_core._api import suppress_langchain_beta_warning
            from langchain_quickjs import CodeInterpreterMiddleware, PTCOption

            ptc_names = _resolve_ptc_option(
                getattr(settings, "interpreter_ptc", None),
                tools=tools_list,
                acknowledge_unsafe=getattr(settings, "interpreter_ptc_acknowledge_unsafe", False),
                auto_approve=auto_approve,
            )
            ptc_option: PTCOption | None = (
                cast("PTCOption", list(ptc_names)) if ptc_names is not None else None
            )

            with suppress_langchain_beta_warning():
                agent_middleware.append(
                    CodeInterpreterMiddleware(
                        tool_name="js_eval",
                        timeout=getattr(settings, "interpreter_timeout_seconds", 30),
                        memory_limit=getattr(settings, "interpreter_memory_limit_mb", 64) * 1024 * 1024,
                        max_ptc_calls=getattr(settings, "interpreter_max_ptc_calls", 50),
                        max_result_chars=getattr(settings, "interpreter_max_result_chars", 50000),
                        ptc=ptc_option,
                    )
                )
        except ImportError:
            logger.warning("langchain-quickjs is not installed. CodeInterpreterMiddleware disabled.")

    # Local Context Injector
    from dcoder.config.langsmith import get_langsmith_project_name
    tracing_project_name = get_langsmith_project_name()
    agent_middleware.append(
        LocalContextMiddleware(
            backend=composite_backend,
            tracing_project=tracing_project_name,
            user_tracing_project=getattr(settings, "user_langchain_project", tracing_project_name),
        )
    )

    # Shell Allow List Middleware
    allow_list = getattr(settings, "shell_allow_list", None) or []
    if allow_list:
        from dcoder.middleware.shell_allow_list import ShellAllowListMiddleware
        agent_middleware.append(ShellAllowListMiddleware(allow_list))

    # Configure HITL interrupts and Auto Mode Middleware
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None
    if auto_approve:
        interrupt_on = {}
    else:
        interrupt_on = {
            "execute": {
                "allowed_decisions": ["approve", "reject"],
                "description": _format_description,
                "when": _should_interrupt_tool_call,
            },
            "write_file": {
                "allowed_decisions": ["approve", "reject"],
                "description": _format_description,
                "when": _should_interrupt_tool_call,
            },
            "edit_file": {
                "allowed_decisions": ["approve", "reject"],
                "description": _format_description,
                "when": _should_interrupt_tool_call,
            },
            "delete": {
                "allowed_decisions": ["approve", "reject"],
                "description": _format_description,
                "when": _should_interrupt_tool_call,
            },
            "web_search": {
                "allowed_decisions": ["approve", "reject"],
                "description": _format_description,
                "when": _should_interrupt_tool_call,
            },
            "fetch_url": {
                "allowed_decisions": ["approve", "reject"],
                "description": _format_description,
                "when": _should_interrupt_tool_call,
            },
            "task": {
                "allowed_decisions": ["approve", "reject"],
                "description": _format_description,
                "when": _should_interrupt_tool_call,
            },
            "start_async_task": {
                "allowed_decisions": ["approve", "reject"],
                "description": _format_description,
                "when": _should_interrupt_tool_call,
            },
            "update_async_task": {
                "allowed_decisions": ["approve", "reject"],
                "description": _format_description,
                "when": _should_interrupt_tool_call,
            },
            "cancel_async_task": {
                "allowed_decisions": ["approve", "reject"],
                "description": _format_description,
                "when": _should_interrupt_tool_call,
            },
            "compact_conversation": {
                "allowed_decisions": ["approve", "reject"],
                "description": _format_description,
                "when": _should_interrupt_tool_call,
            },
        }

    auto_mode_config: tuple[Path, list[str]] | None = None
    if interrupt_on is not None and interactive and not auto_approve:
        auto_mode_config = (Path(effective_cwd), list(allow_list))

    if auto_mode_config is not None and interrupt_on:
        from dcoder.middleware.auto_mode import AutoModeHITLMiddleware
        agent_middleware.append(
            AutoModeHITLMiddleware(
                interrupt_on,
                worktree_root=auto_mode_config[0],
                shell_allow_list=auto_mode_config[1],
            )
        )
    elif interrupt_on is not None:
        from dcoder.middleware.auto_mode import AsyncApprovalHITLMiddleware
        agent_middleware.append(AsyncApprovalHITLMiddleware(interrupt_on))

    from dcoder.middleware.server_hooks import ServerHooksMiddleware
    hooks_cwd = Path(effective_cwd) if effective_cwd else Path.cwd()
    agent_middleware.append(
        ServerHooksMiddleware(cwd=hooks_cwd, mcp_tools=mcp_tools_list)
    )

    # Goal Criteria Generator Middleware — full nested pipeline
    from dcoder.middleware.goal_criteria import (
        GoalCriteriaMiddleware,
        create_goal_criteria_agent,
        create_goal_criteria_fallback_agent,
    )

    criteria_agent = None
    fallback_agent = None
    criteria_context_tools: list[Any] = list(goal_criteria_tools or ())
    # Include MCP tools as context tools for criteria generation if available.
    if not criteria_context_tools and mcp_tools_list:
        criteria_context_tools = list(mcp_tools_list)

    try:
        criteria_agent = create_goal_criteria_agent(
            model=active_model,
            repository_backend=composite_backend,
            repository_root=str(effective_cwd),
            context_tools=criteria_context_tools,
        )
    except Exception as exc:
        logger.warning(
            "Failed to create goal criteria agent: %s; criteria generation "
            "will use the fallback agent",
            exc,
        )

    try:
        fallback_agent = create_goal_criteria_fallback_agent(
            model=active_model,
        )
    except Exception as exc:
        logger.warning(
            "Failed to create goal criteria fallback agent: %s", exc
        )

    agent_middleware.append(
        GoalCriteriaMiddleware(
            criteria_agent=criteria_agent,
            fallback_agent=fallback_agent,
        )
    )

    # Compaction Middleware (after local context and goal criteria)
    agent_middleware.append(
        _create_cli_compaction_middleware(active_model, composite_backend)
    )

    # Reliable Rubric Evaluator Middleware — with grader middleware and context schema
    from dcoder.middleware.goal_criteria import _WebSearchBudgetMiddleware
    from dcoder.rubrics import _create_rubric_grader_tools
    from dcoder.rubrics.evaluator import _RUBRIC_GRADER_SYSTEM_PROMPT

    rubric_grader_tools = _create_rubric_grader_tools(composite_backend)

    grader_middleware: list[AgentMiddleware[Any, Any]] = [
        _WebSearchBudgetMiddleware(),
    ]

    logger.debug(
        "[HITL_TRACE_DEBUG] ReliableRubric Grader Middleware Stack: %s",
        [getattr(m, "name", type(m).__name__) for m in grader_middleware],
    )

    agent_middleware.append(
        ReliableRubricMiddleware(
            model=active_model,
            system_prompt=_RUBRIC_GRADER_SYSTEM_PROMPT,
            tools=rubric_grader_tools,
            grader_middleware=grader_middleware,
            grader_context_schema=CLIContextSchema,
        )
    )

    # Wire Subagents
    if async_subagents is None:
        from dcoder.subagents.loader import load_async_subagents

        async_subagents = load_async_subagents() or None

    from dcoder.subagents import list_subagents, get_built_in_subagents
    user_agents_dir = settings.get_user_agents_dir(assistant_id)
    project_agents_dir = settings.get_project_agents_dir()
    
    custom_subagent_metas = list_subagents(
        user_agents_dir=user_agents_dir,
        project_agents_dir=project_agents_dir,
    )
    built_in_subagent_metas = get_built_in_subagents()
    
    subagent_by_name = {}
    for meta in built_in_subagent_metas:
        name = meta.get("name")
        if name:
            subagent_by_name[name] = meta
    for meta in custom_subagent_metas:
        name = meta.get("name")
        if name:
            subagent_by_name[name] = meta

    main_tool_descriptions = _get_harness_tool_descriptions(active_model)
        
    subagent_interrupt_on = interrupt_on if (interactive and not auto_approve) else None
    compiled_subagents = []
    for name, subagent_meta in subagent_by_name.items():
        if fs_tools is not None and "runnable" in subagent_meta:
            msg = (
                "Cannot enforce --allow-fs-tools on compiled subagent "
                f"{subagent_meta.get('name', '<unnamed>')!r}: its middleware is "
                "not configurable, so the filesystem restriction would be "
                "silently bypassed."
            )
            raise ValueError(msg)

        model_spec = subagent_meta.get("model")
        subagent_dict: dict[str, Any] = {
            "name": subagent_meta.get("name") or name,
            "description": subagent_meta.get("description") or "",
            "system_prompt": subagent_meta.get("system_prompt") or "",
        }
        if model_spec:
            subagent_dict["model"] = model_spec
            
        subagent_name = subagent_meta.get("name") or name
        allow_list = getattr(settings, "shell_allow_list", None) or []
        subagent_middleware = _subagent_cli_middleware(
            has_explicit_model=bool(model_spec),
            assistant_id=assistant_id,
            subagent_name=subagent_name,
            allowed_tools=subagent_meta.get("tools"),
            allowed_skills=subagent_meta.get("skills"),
            interactive=interactive,
            shell_allow_list=allow_list if not interactive and allow_list else None,
            interrupt_on=subagent_interrupt_on,
            worktree_root=effective_cwd,
        )
        if subagent_middleware:
            subagent_dict["middleware"] = subagent_middleware
        if fs_tools is not None:
            from deepagents.middleware import FilesystemMiddleware
            if "middleware" not in subagent_dict:
                subagent_dict["middleware"] = []
            
            subagent_tool_descriptions = (
                _get_harness_tool_descriptions(subagent_dict["model"])
                if "model" in subagent_dict
                else main_tool_descriptions
            )

            kwargs: dict[str, Any] = {
                "backend": composite_backend,
                "tools": fs_tools,
                "custom_tool_descriptions": subagent_tool_descriptions,
            }
            try:
                fs_mw = FilesystemMiddleware(**kwargs)
            except TypeError:
                fs_mw = FilesystemMiddleware(backend=composite_backend)
                fs_mw.tools = [t for t in fs_mw.tools if getattr(t, "name", "") in fs_tools]
                
            mw_list = subagent_dict["middleware"]
            if isinstance(mw_list, list):
                mw_list.append(fs_mw)
        if subagent_interrupt_on is not None:
            subagent_dict["interrupt_on"] = {}

        compiled_subagents.append(subagent_dict)

    from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT

    if not any(
        subagent.get("name") == GENERAL_PURPOSE_SUBAGENT["name"]
        for subagent in compiled_subagents
    ):
        gp_middleware = _subagent_cli_middleware(
            has_explicit_model=False,
            assistant_id=assistant_id,
            subagent_name=GENERAL_PURPOSE_SUBAGENT["name"],
            interactive=interactive,
            interrupt_on=subagent_interrupt_on,
            worktree_root=effective_cwd,
        )
        if fs_tools is not None:
            from deepagents.middleware import FilesystemMiddleware
            kwargs: dict[str, Any] = {
                "backend": composite_backend,
                "tools": fs_tools,
                "custom_tool_descriptions": main_tool_descriptions,
            }
            try:
                fs_mw = FilesystemMiddleware(**kwargs)
            except TypeError:
                fs_mw = FilesystemMiddleware(backend=composite_backend)
                fs_mw.tools = [t for t in fs_mw.tools if getattr(t, "name", "") in fs_tools]
            gp_middleware.append(fs_mw)

        gp_subagent: dict[str, Any] = {
            "name": GENERAL_PURPOSE_SUBAGENT["name"],
            "description": GENERAL_PURPOSE_SUBAGENT["description"],
            "system_prompt": GENERAL_PURPOSE_SUBAGENT["system_prompt"],
            "middleware": gp_middleware,
        }
        if subagent_interrupt_on is not None:
            gp_subagent["interrupt_on"] = {}

        compiled_subagents.append(gp_subagent)

    # 7. System prompt is handled via HarnessProfile (base_system_prompt)
    resolved_system_prompt = None


    all_subagents: list[Any] = [
        *compiled_subagents,
        *(async_subagents or []),
    ]
    logger.debug(
        "[HITL_TRACE_DEBUG] Main Agent Middleware Stack: %s",
        [getattr(m, "name", type(m).__name__) for m in agent_middleware],
    )

    agent = create_deep_agent(
        model=active_model,
        system_prompt=cast(Any, resolved_system_prompt),
        tools=tools_list,
        backend=composite_backend,
        middleware=agent_middleware,
        interrupt_on=None,
        context_schema=CLIContextSchema,
        checkpointer=checkpointer,
        subagents=all_subagents or None,
        name=_sanitize_agent_message_name(assistant_id),
    )
    return agent, composite_backend


create_cli_agent = create_dcoder_agent

