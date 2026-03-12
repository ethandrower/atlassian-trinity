"""Decline a pull request."""

from typing import Any, Dict, Optional
from ..api import BitbucketAPI


def decline_pr(
    api: BitbucketAPI, workspace: str, repo: str, pr_id: int,
    message: Optional[str] = None,
) -> Dict[str, Any]:
    return api.decline_pull_request(workspace, repo, pr_id, message=message)
