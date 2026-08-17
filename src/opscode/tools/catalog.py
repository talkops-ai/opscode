"""Catalog of built-in tools for the opscode agent."""

from opscode.tools.registry import ToolRegistry
from opscode.tools.web_search import web_search
from opscode.tools.fetch_url import fetch_url


def register_all_tools() -> None:
    """Register all available tools with the ToolRegistry."""
    registry = ToolRegistry.get_instance()

    # Core general-purpose tools
    registry.register("web_search", lambda **kwargs: web_search)
    registry.register("fetch_url", lambda **kwargs: fetch_url)

    from opscode.tools.thread import get_current_thread_id

    registry.register("get_current_thread_id", lambda **kwargs: get_current_thread_id)

    # Goal and Rubric tools
    from opscode.tools.goal_tools import get_rubric, get_goal, update_goal

    registry.register("get_rubric", lambda **kwargs: get_rubric)
    registry.register("get_goal", lambda **kwargs: get_goal)
    registry.register("update_goal", lambda **kwargs: update_goal)
