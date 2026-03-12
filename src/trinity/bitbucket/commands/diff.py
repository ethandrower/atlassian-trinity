"""Get the diff or diffstat for a pull request."""

from typing import Any, Union
from ..api import BitbucketAPI


def diff_pr(
    api: BitbucketAPI, workspace: str, repo: str, pr_id: int,
    stat: bool = False,
) -> Union[str, Any]:
    if stat:
        return api.get_diffstat(workspace, repo, pr_id)
    return api.get_diff(workspace, repo, pr_id)
