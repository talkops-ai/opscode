from __future__ import annotations
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence, TYPE_CHECKING

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.pregel import Pregel

if TYPE_CHECKING:
    from dcoder.backend.composite import DCodCompositeBackend

logger = logging.getLogger("dcoder")


@dataclass
class CLIContextSchema:
    model: str | None = None
    model_params: dict[str, Any] = field(default_factory=dict)
    auto_approve: bool = False
    approval_mode_key: str | None = None
    thread_id: str | None = None


def run_sync(coro):
    import asyncio
    try:
        return asyncio.run(coro)
    except RuntimeError:
        import threading
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()


def _should_interrupt_tool_call(request: Any) -> bool:
    """Decide whether a gated tool call should pause for human approval."""
    runtime = getattr(request, "runtime", None)
    ctx = getattr(runtime, "context", None)
    if ctx is not None:
        auto_app = False
        if isinstance(ctx, dict):
            auto_app = bool(ctx.get("auto_approve", False))
        else:
            auto_app = bool(getattr(ctx, "auto_approve", False))
        if auto_app:
            return False

    # Never interrupt internal memory file writes (e.g. AGENTS.md)
    tool_call = getattr(request, "action", None) or getattr(request, "tool_call", None)
    if isinstance(tool_call, dict):
        args = tool_call.get("args") or {}
        path_str = str(args.get("path") or args.get("TargetFile") or "")
        if "AGENTS.md" in path_str:
            return False

    return True


def _format_description(tool_call: Any, state: Any = None, runtime: Any = None) -> str:
    name = tool_call.get("name")
    args = tool_call.get("args") or {}
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
    elif name in ("task", "start_async_task"):
        return f"Spawn subagent: {args.get('name') or args.get('TaskName')}"
    elif name == "update_async_task":
        return f"Update async subagent: {args.get('task_id')}"
    elif name == "cancel_async_task":
        return f"Cancel async subagent: {args.get('task_id')}"
    elif name == "compact_conversation":
        return f"Compact conversation history"
    return f"Execute tool '{name}' with arguments: {args}"


def _subagent_cli_middleware(*, has_explicit_model: bool, assistant_id: str) -> list[Any]:
    from dcoder.middleware.configurable_model import ConfigurableModelMiddleware
    from dcoder.memory.guard import ManagedMemoryGuardMiddleware
    from dcoder.config.settings import settings

    middleware = []
    if not has_explicit_model:
        middleware.append(ConfigurableModelMiddleware(persist_model_state=False))
    
    # Protect AGENTS.md from subagent writes
    memory_sources = [str(settings.get_user_agent_md_path(assistant_id))]
    middleware.append(ManagedMemoryGuardMiddleware(memory_sources))
    return middleware


def create_dcoder_agent(
    model: str | BaseChatModel,
    *,
    assistant_id: str = "dcoder",
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    system_prompt: str | None = None,
    interactive: bool = True,
    auto_approve: bool = False,
    enable_shell: bool = True,
    checkpointer: Any | None = None,
    cwd: str | Path | None = None,
    sandbox: str | None = None,
    thread_id: str | None = None,
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
    from dcoder.prompts.resolver import get_system_prompt
    from dcoder.tools.registry import ToolRegistry
    from dcoder.tools.catalog import register_all_tools

    # 1. Register all tools and build tool list
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
                tools_list.append(registry.build_tool(tool_name))
            except Exception as e:
                logger.warning("Failed to build registered tool %s: %s", tool_name, e)

    # Discovered MCP Configs
    from dcoder.mcp.discovery import MCPDiscovery
    from dcoder.mcp.session_manager import MCPSessionManager
    from dcoder.mcp.trust import is_project_mcp_trusted, compute_config_fingerprint

    discovery = MCPDiscovery()
    mcp_config = discovery.discover()
    
    # Check if project config is trusted
    project_config_path = settings.project_root / ".mcp.json" if settings.project_root else None
    trust_project = True
    if project_config_path and project_config_path.exists():
        fingerprint = compute_config_fingerprint([project_config_path])
        trust_project = is_project_mcp_trusted(str(settings.project_root), fingerprint)
        if not trust_project:
            logger.warning("Project MCP configuration is untrusted. Skipping project-level MCP tools.")
    
    # Initialize MCPSessionManager
    mcp_manager = MCPSessionManager(mcp_config)
    
    # Connect and get tools
    mcp_tools = []
    if mcp_config:
        try:
            mcp_tools = run_sync(mcp_manager.connect_all(trust_project=trust_project))
            tools_list.extend(mcp_tools)
        except Exception as e:
            logger.warning("Failed to connect to MCP servers: %s", e)

    # 2. Ensure dcoder agent directory exists
    settings.ensure_agent_dir(assistant_id)

    # 3. Resolve model if it was passed as string spec
    if isinstance(model, str):
        model_res = create_model(model)
        model_res.apply_to_settings()
        active_model = model_res.model
    else:
        active_model = model

    # 4. Select working directory
    effective_cwd = Path(cwd) if cwd is not None else (settings.project_root or Path.cwd())

    # Resolve checkpointer if None
    # We default checkpointer to None as it is managed by the server subprocess.

    # 5. Initialize backend
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

    # 6. Build middleware stack from registry
    exclude_middleware = set()
    middleware_kwargs = {}
    if interactive:
        exclude_middleware.add("shell_allow_list")
    else:
        allow_list = getattr(settings, "shell_allow_list", None) or []
        middleware_kwargs["shell_allow_list"] = {"allow_list": allow_list}

    middleware_kwargs["mcp"] = {"session_manager": mcp_manager, "mcp_config": mcp_config}

    agent_middleware: list[Any] = get_middleware_registry().build_stack(
        exclude=exclude_middleware,
        **middleware_kwargs
    )

    # Wire Memory & Guard
    from dcoder.memory import MemoryRegistry, ManagedMemoryGuardMiddleware
    from deepagents.middleware import MemoryMiddleware
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
            ManagedMemoryGuardMiddleware(memory_sources_str)
        )

    # Wire Skills
    from dcoder.skills import SkillRegistry
    from dcoder.middleware import PluginSkillsMiddleware
    SkillRegistry.get_instance().discover_skills()
    skill_sources = SkillRegistry.get_instance().get_sources_for_middleware()
    if skill_sources:
        agent_middleware.append(
            PluginSkillsMiddleware(
                backend=FilesystemBackend(virtual_mode=False),
                sources=skill_sources,
            )
        )



    # Wire Rubrics & Goal Tools
    from dcoder.rubrics import RubricMiddleware, _create_rubric_grader_tools
    from dcoder.rubrics.goal_tools import GoalToolsMiddleware
    from dcoder.rubrics.evaluator import _RUBRIC_GRADER_SYSTEM_PROMPT
    agent_middleware.append(GoalToolsMiddleware())
    
    rubric_kwargs = {
        "model": active_model,
        "system_prompt": _RUBRIC_GRADER_SYSTEM_PROMPT,
        "tools": _create_rubric_grader_tools(composite_backend),
    }
    agent_middleware.append(RubricMiddleware(**rubric_kwargs))

    # Wire Subagents
    from dcoder.subagents import list_subagents, get_built_in_subagents
    user_agents_dir = settings.user_dcoder_dir / assistant_id / "agents"
    project_agents_dir = settings.project_root / ".dcoder" / "agents" if settings.project_root else None
    
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
        
    compiled_subagents = []
    for name, subagent_meta in subagent_by_name.items():
        model_spec = subagent_meta.get("model")
        subagent_dict = {
            "name": subagent_meta.get("name") or name,
            "description": subagent_meta.get("description") or "",
            "system_prompt": subagent_meta.get("system_prompt") or "",
        }
        if model_spec:
            subagent_dict["model"] = model_spec
            
        subagent_middleware = _subagent_cli_middleware(
            has_explicit_model=bool(model_spec),
            assistant_id=assistant_id,
        )
        if subagent_middleware:
            subagent_dict["middleware"] = subagent_middleware
            
        compiled_subagents.append(subagent_dict)

    # 7. Generate or use custom system prompt
    if system_prompt is None:
        system_prompt = get_system_prompt(
            assistant_id=assistant_id,
            interactive=interactive,
            cwd=effective_cwd,
        )

    # 8. Configure HITL interrupts
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

    # 9. Compile using deepagents SDK
    agent = create_deep_agent(
        model=active_model,
        system_prompt=system_prompt,
        tools=tools_list,
        backend=composite_backend,
        middleware=agent_middleware,
        interrupt_on=interrupt_on,
        context_schema=CLIContextSchema,
        checkpointer=checkpointer,
        subagents=compiled_subagents or None,
        name=assistant_id,
    )

    return agent, composite_backend
