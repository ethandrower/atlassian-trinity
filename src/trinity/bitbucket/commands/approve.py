"""Approve / unapprove a pull request."""

from typing import Any, Dict
from ..api import BitbucketAPI


def approve_pr(api: BitbucketAPI, workspace: str, repo: str, pr_id: int) -> Dict[str, Any]:
    return api.approve_pull_request(workspace, repo, pr_id)


def unapprove_pr(api: BitbucketAPI, workspace: str, repo: str, pr_id: int) -> Dict[str, Any]:
    return api.unapprove_pull_request(workspace, repo, pr_id)
