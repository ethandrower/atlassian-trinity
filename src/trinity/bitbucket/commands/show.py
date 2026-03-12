"""Show a pull request."""

import webbrowser
from typing import Any, Dict, Optional
from ..api import BitbucketAPI


def show_pr(
    api: BitbucketAPI,
    workspace: str,
    repo: str,
    pr_id: int,
    web: bool = False,
    include_comments: bool = False,
) -> Dict[str, Any]:
    pr = api.get_pull_request(workspace, repo, pr_id)

    if include_comments:
        pr["comments"] = api.get_comments(workspace, repo, pr_id)

    if web:
        html_url = pr.get("links", {}).get("html", {}).get("href")
        if html_url:
            webbrowser.open(html_url)

    return pr
