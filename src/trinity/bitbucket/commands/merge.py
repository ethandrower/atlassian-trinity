"""Merge a pull request."""

from typing import Any, Dict, Optional
from ..api import BitbucketAPI


def merge_pr(
    api: BitbucketAPI, workspace: str, repo: str, pr_id: int,
    message: Optional[str] = None,
    strategy: str = "merge_commit",
    close_branch: bool = False,
) -> Dict[str, Any]:
    return api.merge_pull_request(
        workspace, repo, pr_id,
        message=message,
        merge_strategy=strategy,
        close_source_branch=close_branch,
    )
