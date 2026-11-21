"""Request changes on / clear a change request for a pull request."""

from typing import Any, Dict
from ..api import BitbucketAPI


def request_changes_pr(api: BitbucketAPI, workspace: str, repo: str, pr_id: int) -> Dict[str, Any]:
    return api.request_changes_pull_request(workspace, repo, pr_id)


def unrequest_changes_pr(api: BitbucketAPI, workspace: str, repo: str, pr_id: int) -> Dict[str, Any]:
    return api.remove_change_request_pull_request(workspace, repo, pr_id)
