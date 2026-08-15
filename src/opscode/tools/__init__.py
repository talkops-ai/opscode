"""Tools catalog and registry for the opscode agent."""

from opscode.tools.registry import ToolRegistry
from opscode.tools.web_search import web_search
from opscode.tools.fetch_url import fetch_url
from opscode.tools.goal_tools import get_rubric, get_goal, update_goal
from opscode.tools.thread import get_current_thread_id

__all__ = [
    "ToolRegistry",
    "web_search",
    "fetch_url",
    "get_rubric",
    "get_goal",
    "update_goal",
    "get_current_thread_id",
]
