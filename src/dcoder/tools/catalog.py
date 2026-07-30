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
    
    # DevOps-specific tools
    from dcoder.tools.devops.terraform import (
        terraform_validate,
        terraform_plan,
        terraform_fmt,
    )
    from dcoder.tools.devops.helm import helm_lint, helm_template
    from dcoder.tools.devops.kubectl import (
        kubectl_get,
        kubectl_describe,
        kubectl_logs,
    )
    from dcoder.tools.devops.ansible import ansible_check
    from dcoder.tools.devops.argocd import argocd_diff

    registry.register("terraform_validate", lambda **kwargs: terraform_validate)
    registry.register("terraform_plan", lambda **kwargs: terraform_plan)
    registry.register("terraform_fmt", lambda **kwargs: terraform_fmt)
    
    registry.register("helm_lint", lambda **kwargs: helm_lint)
    registry.register("helm_template", lambda **kwargs: helm_template)
    
    registry.register("kubectl_get", lambda **kwargs: kubectl_get)
    registry.register("kubectl_describe", lambda **kwargs: kubectl_describe)
    registry.register("kubectl_logs", lambda **kwargs: kubectl_logs)
    
    registry.register("ansible_check", lambda **kwargs: ansible_check)
    registry.register("argocd_diff", lambda **kwargs: argocd_diff)
