"""Update a pull request."""

from typing import Any, Dict, List, Optional

from ..api import BitbucketAPI
from ..reviewers import ReviewerResolver, merge_reviewers, split_names


def update_pr(
    api: BitbucketAPI, workspace: str, repo: str, pr_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    dest: Optional[str] = None,
    add_reviewers: Optional[List[str]] = None,
    remove_reviewers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Change title/description/destination and add or remove reviewers.

    Reviewers are added to the PR's current list, never swapped for it.
    """
    kwargs: dict = {}
    if title:
        kwargs["title"] = title
    if description is not None:
        kwargs["description"] = description
    if dest:
        kwargs["destination_branch"] = dest

    add_names = split_names(add_reviewers or [])
    remove_names = split_names(remove_reviewers or [])
    if add_names or remove_names:
        current = api.get_pull_request(workspace, repo, pr_id)
        resolver = ReviewerResolver(api, workspace, repo)
        reviewers, _ = merge_reviewers(
            current.get("reviewers") or [],
            add=resolver.resolve_all(add_names),
            remove=resolver.resolve_all(remove_names),
            author_uuid=(current.get("author") or {}).get("uuid"),
        )
        kwargs["reviewers"] = reviewers
        # Send the current title/description too so the PUT can't blank them.
        kwargs.setdefault("title", current.get("title"))
        if "description" not in kwargs:
            kwargs["description"] = current.get("description") or ""

    if not kwargs:
        return api.get_pull_request(workspace, repo, pr_id)

    return api.update_pull_request(workspace, repo, pr_id, **kwargs)
