"""
Regression tests for cli._bb_context — the workspace/repo resolution
behind `trinity bb`.

The bug these cover: _bb_context used to read the workspace only from the
-w flag and $BITBUCKET_WORKSPACE, then try the git remote. It never
consulted bitbucket.workspace in the config file. Run `trinity bb -r
citemed_web show 476` from a directory that isn't a Bitbucket clone and
the workspace resolved to "", producing the URL

    /repositories//citemed_web/pullrequests/476

Bitbucket answers that with a plain 404, which surfaces as "Resource not
found" — indistinguishable from a PR that genuinely doesn't exist.

The empty workspace also broke per-repo token routing: the API client
picks a token by matching the /repositories/{ws}/{repo} prefix, so a
blank workspace made that lookup miss and silently fall back to the
global token.

The equivalent chain in bb_compat._resolve_repo always did consult the
config; both now share trinity.base.repo_context.
"""

from types import SimpleNamespace

import pytest

from trinity import cli
from trinity.base import repo_context


def _ctx(workspace=None, repo=None) -> SimpleNamespace:
    return SimpleNamespace(obj={"bb_workspace": workspace, "bb_repo": repo})


@pytest.fixture(autouse=True)
def _no_git_remote(monkeypatch):
    """Simulate running from outside any git repo, which is where the
    original bug showed up."""

    class _NotARepo:
        def __init__(self, *a, **kw):
            raise RuntimeError("not a git repo")

    monkeypatch.setattr("git.Repo", _NotARepo)
    monkeypatch.delenv("BITBUCKET_WORKSPACE", raising=False)
    monkeypatch.delenv("BITBUCKET_DEFAULT_REPO", raising=False)


def test_workspace_falls_back_to_config_outside_a_git_repo(monkeypatch):
    """The original failure: -r given, no -w, not in a clone."""
    monkeypatch.setattr(repo_context, "get_workspace", lambda: "citemed")
    monkeypatch.setattr(repo_context, "get_default_repo", lambda: None)

    ws, repo = cli._bb_context(_ctx(repo="citemed_web"))

    assert (ws, repo) == ("citemed", "citemed_web")


def test_resolved_workspace_produces_a_routable_slug(monkeypatch):
    """Guard the second-order effect — a blank workspace defeats per-repo
    token selection, so assert the endpoint the API client would build
    actually carries a slug it can match."""
    from trinity.bitbucket.api import _slug_from_endpoint

    monkeypatch.setattr(repo_context, "get_workspace", lambda: "citemed")
    monkeypatch.setattr(repo_context, "get_default_repo", lambda: None)

    ws, repo = cli._bb_context(_ctx(repo="ai_backend"))
    endpoint = f"/repositories/{ws}/{repo}/pullrequests/62"

    assert "//" not in endpoint
    assert _slug_from_endpoint(endpoint) == "citemed/ai_backend"


def test_explicit_workspace_flag_beats_config(monkeypatch):
    monkeypatch.setattr(repo_context, "get_workspace", lambda: "config-ws")
    monkeypatch.setattr(repo_context, "get_default_repo", lambda: None)

    ws, repo = cli._bb_context(_ctx(workspace="flag-ws", repo="some-repo"))

    assert (ws, repo) == ("flag-ws", "some-repo")


def test_repo_falls_back_to_config_default_repo(monkeypatch):
    monkeypatch.setattr(repo_context, "get_workspace", lambda: "citemed")
    monkeypatch.setattr(repo_context, "get_default_repo", lambda: "citemed_web")

    ws, repo = cli._bb_context(_ctx())

    assert (ws, repo) == ("citemed", "citemed_web")


def test_unresolvable_returns_empty_strings(monkeypatch):
    """_bb_context reports rather than raises; callers decide."""
    monkeypatch.setattr(repo_context, "get_workspace", lambda: None)
    monkeypatch.setattr(repo_context, "get_default_repo", lambda: None)

    assert cli._bb_context(_ctx()) == ("", "")


def test_git_remote_still_wins_over_config(monkeypatch):
    """Inside a clone, the repo you're standing in is the better answer —
    this is the pre-existing behavior the fix must not disturb."""
    monkeypatch.setattr(repo_context, "get_workspace", lambda: "config-ws")
    monkeypatch.setattr(repo_context, "get_default_repo", lambda: "config-repo")

    class _Remote:
        url = "git@bitbucket.org:remote-ws/remote-repo.git"

    class _Repo:
        def __init__(self, *a, **kw):
            self.remotes = [_Remote()]

    monkeypatch.setattr("git.Repo", _Repo)

    ws, repo = cli._bb_context(_ctx())

    assert (ws, repo) == ("remote-ws", "remote-repo")
