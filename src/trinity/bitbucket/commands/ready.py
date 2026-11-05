"""Take a pull request out of draft and add the team's reviewers."""

from typing import Any, Dict, List, Optional

from ..api import BitbucketAPI
from ..reviewers import (
    ReviewerResolver,
    default_reviewers,
    merge_reviewers,
    pm_reviewers,
    split_names,
)


def _people(pr: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"uuid": r.get("uuid"), "display_name": r.get("display_name"),
         "nickname": r.get("nickname")}
        for r in pr.get("reviewers") or []
    ]


def ready_pr(
    api: BitbucketAPI, workspace: str, repo: str, pr_id: int,
    client_visible: bool = False,
    reviewers: Optional[List[str]] = None,
    use_defaults: bool = True,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Mark the PR ready for review and add reviewers, in one PUT.

    Adds bitbucket.default_reviewers (unless use_defaults is False), plus
    bitbucket.pm_reviewers when client_visible, plus any explicit reviewers.
    Keeps every existing reviewer, skips the PR author, and leaves the title
    and description as they are. Running it twice changes nothing the second
    time: no PUT is sent when the PR is already ready and has everyone.
    """
    current = api.get_pull_request(workspace, repo, pr_id)

    names: List[str] = []
    if use_defaults:
        names += default_reviewers(cfg)
    if client_visible:
        names += pm_reviewers(cfg)
    names += split_names(reviewers or [])

    resolver = ReviewerResolver(api, workspace, repo, cfg=cfg)
    wanted = resolver.resolve_all(names)
    author_uuid = (current.get("author") or {}).get("uuid")
    merged, summary = merge_reviewers(
        current.get("reviewers") or [], add=wanted, author_uuid=author_uuid,
    )

    was_draft = bool(current.get("draft"))
    changed = was_draft or bool(summary["added"])
    if changed:
        result = api.update_pull_request(
            workspace, repo, pr_id,
            title=current.get("title"),
            description=current.get("description") or "",
            reviewers=merged,
            draft=False,
        )
    else:
        result = current

    return {
        "id": result.get("id", pr_id),
        "title": result.get("title"),
        "state": result.get("state"),
        "draft": bool(result.get("draft")),
        "was_draft": was_draft,
        "changed": changed,
        "url": (result.get("links") or {}).get("html", {}).get("href"),
        "author": (current.get("author") or {}).get("display_name"),
        "reviewers": _people(result),
        "added": summary["added"],
        "skipped_author": summary["skipped_author"],
        "client_visible": client_visible,
    }
