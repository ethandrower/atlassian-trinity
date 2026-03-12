"""Update a pull request."""

from typing import Any, Dict, List, Optional
from ..api import BitbucketAPI


def update_pr(
    api: BitbucketAPI, workspace: str, repo: str, pr_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    dest: Optional[str] = None,
    add_reviewers: Optional[List[str]] = None,
    remove_reviewers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    kwargs: dict = {}
    if title:
        kwargs["title"] = title
    if description is not None:
        kwargs["description"] = description
    if dest:
        kwargs["destination_branch"] = dest

    if add_reviewers or remove_reviewers:
        current = api.get_pull_request(workspace, repo, pr_id)
        current_reviewers = {u.get("username") or u.get("uuid") for u in current.get("reviewers", [])}
        if add_reviewers:
            current_reviewers.update(add_reviewers)
        if remove_reviewers:
            current_reviewers -= set(remove_reviewers)
        kwargs["reviewers"] = [{"username": r} for r in current_reviewers]

    if not kwargs:
        return api.get_pull_request(workspace, repo, pr_id)

    return api.update_pull_request(workspace, repo, pr_id, **kwargs)
