"""Add a comment to a pull request."""

from typing import Any, Dict, Optional
from ..api import BitbucketAPI


def comment_pr(
    api: BitbucketAPI, workspace: str, repo: str, pr_id: int,
    message: str,
    file: Optional[str] = None,
    line: Optional[int] = None,
    from_line: Optional[int] = None,
    to_line: Optional[int] = None,
    reply_to: Optional[int] = None,
) -> Dict[str, Any]:
    return api.add_comment(
        workspace, repo, pr_id, message,
        file=file, line=line,
        from_line=from_line, to_line=to_line,
        reply_to=reply_to,
    )
