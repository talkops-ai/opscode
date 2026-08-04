"""Catalog of all built-in and DevOps tools for the dcoder agent."""

from dcoder.tools.registry import ToolRegistry
from dcoder.tools.web_search import web_search
from dcoder.tools.fetch_url import fetch_url

def register_all_tools() -> None:
    """Register all available tools with the ToolRegistry."""
    registry = ToolRegistry.get_instance()
    
    # Core general-purpose tools
    registry.register("web_search", lambda **kwargs: web_search)
    registry.register("fetch_url", lambda **kwargs: fetch_url)
    
    from dcoder.tools.thread import get_current_thread_id
    registry.register("get_current_thread_id", lambda **kwargs: get_current_thread_id)
    
    # Goal and Rubric tools
    from dcoder.tools.goal_tools import get_rubric, get_goal, update_goal
    registry.register("get_rubric", lambda **kwargs: get_rubric)
    registry.register("get_goal", lambda **kwargs: get_goal)
    registry.register("update_goal", lambda **kwargs: update_goal)
    
    # DevOps-specific tools
    from dcoder.tools.devops.terraform import (
        create_terraform_validate_tool,
        create_terraform_plan_tool,
        create_terraform_fmt_tool,
    )
    from dcoder.tools.devops.helm import create_helm_lint_tool, create_helm_template_tool
    from dcoder.tools.devops.kubectl import (
        create_kubectl_get_tool,
        create_kubectl_describe_tool,
        create_kubectl_logs_tool,
    )
    from dcoder.tools.devops.ansible import create_ansible_check_tool
    from dcoder.tools.devops.argocd import create_argocd_diff_tool

    registry.register("terraform_validate", create_terraform_validate_tool)
    registry.register("terraform_plan", create_terraform_plan_tool)
    registry.register("terraform_fmt", create_terraform_fmt_tool)
    
    registry.register("helm_lint", create_helm_lint_tool)
    registry.register("helm_template", create_helm_template_tool)
    
    registry.register("kubectl_get", create_kubectl_get_tool)
    registry.register("kubectl_describe", create_kubectl_describe_tool)
    registry.register("kubectl_logs", create_kubectl_logs_tool)
    
    registry.register("ansible_check", create_ansible_check_tool)
    registry.register("argocd_diff", create_argocd_diff_tool)
