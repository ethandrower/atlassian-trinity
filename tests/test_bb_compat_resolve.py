"""
Unit tests for bb_compat._resolve_repo — the workspace/repo resolution
chain used by every `bb` subcommand.

Priority under test (each step only fills in what's still missing):
  1. ctx.obj["workspace"] / ctx.obj["repo"]   (-w / -R flags)
  2. Current git remote
  3. config: bitbucket.workspace + bitbucket.default_repo

When require=True and resolution fails, the helper exits with code 2
and an actionable message.
"""

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from trinity import bb_compat


def _ctx(workspace=None, repo=None) -> SimpleNamespace:
    return SimpleNamespace(obj={"workspace": workspace, "repo": repo})


def _no_git_remote():
    """Patch git.Repo so _resolve_repo never picks up a real remote."""
    return patch.object(bb_compat, "re", bb_compat.re)  # no-op default


@pytest.fixture(autouse=True)
def _block_git_remote(monkeypatch):
    """Force the git-remote branch to no-op for the unit tests so we're
    only asserting on the flag → config chain."""
    class _BadRepo:
        def __init__(self, *a, **kw):
            raise RuntimeError("not a git repo")

    monkeypatch.setattr("git.Repo", _BadRepo)


def test_flags_used_when_present(monkeypatch):
    monkeypatch.delenv("BITBUCKET_DEFAULT_REPO", raising=False)
    monkeypatch.delenv("BITBUCKET_WORKSPACE", raising=False)
    ws, repo = bb_compat._resolve_repo(_ctx("ws-flag", "repo-flag"))
    assert (ws, repo) == ("ws-flag", "repo-flag")


def test_falls_back_to_config_default_repo(monkeypatch):
    monkeypatch.delenv("BITBUCKET_DEFAULT_REPO", raising=False)
    monkeypatch.setenv("BITBUCKET_WORKSPACE", "from-env-ws")
    monkeypatch.setattr(bb_compat, "get_default_repo", lambda: "from-config-repo")
    ws, repo = bb_compat._resolve_repo(_ctx())
    assert (ws, repo) == ("from-env-ws", "from-config-repo")


def test_default_repo_with_workspace_prefix(monkeypatch):
    """default_repo can be 'ws/repo' shorthand."""
    monkeypatch.setattr(bb_compat, "get_workspace", lambda: None)
    monkeypatch.setattr(bb_compat, "get_default_repo", lambda: "other-ws/some-repo")
    ws, repo = bb_compat._resolve_repo(_ctx())
    assert (ws, repo) == ("other-ws", "some-repo")


def test_flag_workspace_overrides_config(monkeypatch):
    monkeypatch.setattr(bb_compat, "get_workspace", lambda: "config-ws")
    monkeypatch.setattr(bb_compat, "get_default_repo", lambda: "config-repo")
    ws, repo = bb_compat._resolve_repo(_ctx(workspace="flag-ws"))
    assert (ws, repo) == ("flag-ws", "config-repo")


def test_exits_with_clear_error_when_unresolvable(monkeypatch, capsys):
    monkeypatch.setattr(bb_compat, "get_workspace", lambda: None)
    monkeypatch.setattr(bb_compat, "get_default_repo", lambda: None)
    with pytest.raises(SystemExit) as excinfo:
        bb_compat._resolve_repo(_ctx())
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "No Bitbucket repo specified" in out
    assert "-R" in out
    assert "BITBUCKET_DEFAULT_REPO" in out
    assert "default_repo" in out


def test_require_false_returns_empty_strings_silently(monkeypatch):
    monkeypatch.setattr(bb_compat, "get_workspace", lambda: None)
    monkeypatch.setattr(bb_compat, "get_default_repo", lambda: None)
    ws, repo = bb_compat._resolve_repo(_ctx(), require=False)
    assert (ws, repo) == ("", "")
