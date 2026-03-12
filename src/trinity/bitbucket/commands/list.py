"""List pull requests."""

from typing import Any, Dict, List, Optional
from ..api import BitbucketAPI


def list_prs(
    api: BitbucketAPI,
    workspace: str,
    repo: str,
    state: str = "OPEN",
    author: Optional[str] = None,
    reviewer: Optional[str] = None,
    limit: int = 25,
    fetch_all: bool = False,
) -> List[Dict[str, Any]]:
    return api.list_pull_requests(
        workspace, repo,
        state=state, author=author, reviewer=reviewer,
        limit=limit, fetch_all=fetch_all,
    )
