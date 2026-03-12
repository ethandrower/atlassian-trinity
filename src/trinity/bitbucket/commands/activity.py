"""Get the activity timeline for a pull request."""

from typing import Any, List
from ..api import BitbucketAPI


def activity_pr(
    api: BitbucketAPI, workspace: str, repo: str, pr_id: int,
    limit: int = 50,
) -> List[Any]:
    activity = api.get_activity(workspace, repo, pr_id)
    return activity[:limit] if limit else activity
