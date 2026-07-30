"""Tools catalog and registry for the dcoder agent."""

from dcoder.tools.registry import ToolRegistry
from dcoder.tools.web_search import web_search
from dcoder.tools.fetch_url import fetch_url

__all__ = [
    "ToolRegistry",
    "web_search",
    "fetch_url",
]
