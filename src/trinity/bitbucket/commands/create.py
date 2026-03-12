"""Create a pull request."""

import webbrowser
from typing import Any, Dict, List, Optional

from ..api import BitbucketAPI

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


def _resolve_reviewers(api: BitbucketAPI, workspace: str, reviewer_names: List[str]) -> List[Dict]:
    resolved = []
    for name in reviewer_names:
        try:
            user = api.get(f"/users/{name}")
            resolved.append({"uuid": user.get("uuid")})
        except Exception:
            resolved.append({"username": name})
    return resolved


def create_pr(
    api: BitbucketAPI,
    workspace: str,
    repo: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    source: Optional[str] = None,
    dest: Optional[str] = "main",
    reviewers: Optional[str] = None,
    close_branch: bool = False,
    web: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    source_branch = source or _current_branch() or "main"

    reviewer_list = []
    if reviewers:
        names = [r.strip() for r in reviewers.split(",")]
        reviewer_list = _resolve_reviewers(api, workspace, names)

    pr = api.create_pull_request(
        workspace, repo,
        title=title or f"PR from {source_branch}",
        description=description or "",
        source_branch=source_branch,
        destination_branch=dest or "main",
        close_source_branch=close_branch,
        reviewers=reviewer_list or None,
    )

    if web:
        html_url = pr.get("links", {}).get("html", {}).get("href")
        if html_url:
            webbrowser.open(html_url)

    return pr
