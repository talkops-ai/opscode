"""Tools catalog and registry for the dcoder agent."""

from dcoder.tools.registry import ToolRegistry
from dcoder.tools.web_search import web_search
from dcoder.tools.fetch_url import fetch_url
from dcoder.tools.goal_tools import get_rubric, get_goal, update_goal
from dcoder.tools.thread import get_current_thread_id

__all__ = [
    "ToolRegistry",
    "web_search",
    "fetch_url",
    "get_rubric",
    "get_goal",
    "update_goal",
    "get_current_thread_id",
]
