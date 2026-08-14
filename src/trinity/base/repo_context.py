"""Shared workspace/repo resolution for Bitbucket commands.

Both CLI front-ends (``trinity bb`` in cli.py and the gh-style ``bb`` in
bb_compat.py) need to answer the same question: which workspace/repo is
this command aimed at? They used to answer it with two separate copies of
the logic, and the copies drifted — cli.py's never consulted the config
file, so running ``trinity bb`` from outside a Bitbucket clone produced a
URL like ``/repositories//repo/...`` with an empty workspace. Bitbucket
answers that with a generic 404, which reads as "no such pull request"
rather than "I don't know which workspace you mean".

The empty workspace had a second-order effect worth remembering: the API
client routes per-repo access tokens by matching the
``/repositories/{ws}/{repo}`` prefix of the outgoing URL, so a blank
workspace also defeated per-repo token selection and silently fell back
to the global token — a second wrong answer stacked on the first.

Keeping the resolution in one place is what stops that from happening
again.
"""

import re
from typing import Optional, Tuple

from .auth import get_default_repo, get_workspace


def _from_git_remote(
    workspace: Optional[str], repo: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
    """Fill in whatever is missing from a bitbucket.org git remote.

    Best-effort: not being in a git repo, or being in one with no
    Bitbucket remote, is a normal situation rather than an error.
    """
    if workspace and repo:
        return workspace, repo
    try:
        from git import Repo

        git_repo = Repo(search_parent_directories=True)
        for remote in git_repo.remotes:
            m = re.search(r"bitbucket\.org[:/]([^/]+)/([^/.]+)", remote.url)
            if m:
                workspace = workspace or m.group(1)
                repo = repo or m.group(2)
                break
    except Exception:
        pass
    return workspace, repo


def _from_config(
    workspace: Optional[str], repo: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
    """Fill in whatever is still missing from ~/.trinity/config.yaml."""
    if not workspace:
        workspace = get_workspace() or None
    if not repo:
        default = get_default_repo()
        if default:
            # Accept "workspace/repo" or a bare "repo" — mirrors the
            # shorthand the -R flag takes.
            if "/" in default:
                ws_default, _, repo_default = default.partition("/")
                workspace = workspace or ws_default
                repo = repo_default
            else:
                repo = default
    return workspace, repo


def resolve_workspace_repo(
    workspace: Optional[str] = None,
    repo: Optional[str] = None,
) -> Tuple[str, str]:
    """Resolve the target workspace/repo, filling gaps in priority order.

    Each step only supplies what is still missing, so an explicit flag is
    never overridden by a weaker source:

      1. Explicit values (``-w`` / ``-r`` / ``-R`` flags, or the
         ``BITBUCKET_WORKSPACE`` env var the callers read into ``workspace``)
      2. The current git remote, when run inside a Bitbucket clone
      3. Config — ``bitbucket.workspace`` and ``bitbucket.default_repo``

    The git remote deliberately outranks the config: inside a checkout,
    the repo you are standing in is a better answer than a global
    default, and taking the workspace from one source and the repo from
    another is how you get a valid-looking URL pointing at a repo that
    does not exist.

    Returns a ``(workspace, repo)`` tuple, using ``""`` for anything that
    could not be resolved so callers can test truthiness and produce
    their own error message.
    """
    workspace, repo = _from_git_remote(workspace, repo)
    workspace, repo = _from_config(workspace, repo)
    return workspace or "", repo or ""
