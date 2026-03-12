"""Trinity Confluence module — Confluence Cloud REST API."""

from .get_page import get_confluence_page
from .create_page import create_confluence_page
from .update_page import update_confluence_page
from .search import search_confluence
from .get_spaces import get_confluence_spaces
from .get_children import get_page_children
from .add_comment import add_confluence_comment

__all__ = [
    "get_confluence_page",
    "create_confluence_page",
    "update_confluence_page",
    "search_confluence",
    "get_confluence_spaces",
    "get_page_children",
    "add_confluence_comment",
]
