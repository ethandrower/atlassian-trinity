"""Create a pull request."""

import webbrowser
from typing import Any, Dict, List, Optional

from ..api import BitbucketAPI
from ..reviewers import ReviewerResolver, normalize_uuid, split_names

try:
    from git import Repo, InvalidGitRepositoryError
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


def _current_branch() -> Optional[str]:
    if not GIT_AVAILABLE:
        return None
    try:
        repo = Repo(search_parent_directories=True)
        return repo.active_branch.name
    except Exception:
        return None


def _current_user_uuid(api: BitbucketAPI) -> Optional[str]:
    """The account that will author the PR; Bitbucket rejects it as a reviewer."""
    try:
        return normalize_uuid(api.get_current_user().get("uuid") or "")
    except Exception:
        return None


def create_pr(
    api: BitbucketAPI,
    workspace: str,
    repo: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    source: Optional[str] = None,
    dest: Optional[str] = "main",
    reviewers: Optional[Any] = None,
    close_branch: bool = False,
    web: bool = False,
    draft: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    source_branch = source or _current_branch() or "main"

    # `reviewers` is a comma-separated string (old --reviewers) or a list
    # (repeatable --reviewer); either may hold UUIDs, aliases or nicknames.
    reviewer_list = []
    if reviewers:
        names = split_names([reviewers] if isinstance(reviewers, str) else reviewers)
        uuids = ReviewerResolver(api, workspace, repo).resolve_all(names)
        author = _current_user_uuid(api)
        reviewer_list = [{"uuid": u} for u in uuids if u != author]

    pr = api.create_pull_request(
        workspace, repo,
        title=title or f"PR from {source_branch}",
        description=description or "",
        source_branch=source_branch,
        destination_branch=dest or "main",
        close_source_branch=close_branch,
        reviewers=reviewer_list or None,
        draft=draft,
    )

    if web:
        html_url = pr.get("links", {}).get("html", {}).get("href")
        if html_url:
            webbrowser.open(html_url)

    return pr
