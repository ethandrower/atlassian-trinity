"""
Unit tests for the Bitbucket repo / token resolution logic added in #2.

Covers:
  - Per-repo bearer token lookup (bitbucket.repo_tokens["ws/repo"])
  - Fallback to the global repo_token when slug not in map
  - Fallback to App Password when no bearer is configured
  - get_default_repo() env + config priority
  - _slug_from_endpoint() for /repositories/{ws}/{repo}/... endpoints
"""

import base64

import pytest

from trinity.base.auth import (
    get_bitbucket_auth_headers,
    get_default_repo,
)
from trinity.bitbucket.api import _slug_from_endpoint


# ── Per-repo bearer routing ────────────────────────────────────────────


def _cfg(**bb) -> dict:
    return {"bitbucket": bb}


def test_per_repo_token_used_when_slug_matches():
    cfg = _cfg(
        repo_token="GLOBAL",
        repo_tokens={"citemed/citemed_web": "PER_REPO_WEB"},
    )
    h = get_bitbucket_auth_headers(config=cfg, repo="citemed/citemed_web")
    assert h["Authorization"] == "Bearer PER_REPO_WEB"


def test_global_token_used_when_slug_unknown():
    cfg = _cfg(
        repo_token="GLOBAL",
        repo_tokens={"citemed/citemed_web": "PER_REPO_WEB"},
    )
    h = get_bitbucket_auth_headers(config=cfg, repo="citemed/other-repo")
    assert h["Authorization"] == "Bearer GLOBAL"


def test_global_token_used_when_no_repo_passed():
    cfg = _cfg(
        repo_token="GLOBAL",
        repo_tokens={"citemed/citemed_web": "PER_REPO_WEB"},
    )
    h = get_bitbucket_auth_headers(config=cfg)
    assert h["Authorization"] == "Bearer GLOBAL"


def test_app_password_fallback_when_no_bearer(monkeypatch):
    monkeypatch.delenv("BITBUCKET_REPO_TOKEN", raising=False)
    monkeypatch.delenv("BITBUCKET_USERNAME", raising=False)
    monkeypatch.delenv("BITBUCKET_APP_PASSWORD", raising=False)
    cfg = _cfg(username="alice", app_password="hunter2")
    h = get_bitbucket_auth_headers(config=cfg)
    expected = "Basic " + base64.b64encode(b"alice:hunter2").decode()
    assert h["Authorization"] == expected


def test_per_repo_token_takes_priority_over_global_and_basic(monkeypatch):
    monkeypatch.delenv("BITBUCKET_REPO_TOKEN", raising=False)
    cfg = _cfg(
        repo_token="GLOBAL",
        username="alice",
        app_password="hunter2",
        repo_tokens={"citemed/foo": "PER_REPO_FOO"},
    )
    h = get_bitbucket_auth_headers(config=cfg, repo="citemed/foo")
    assert h["Authorization"] == "Bearer PER_REPO_FOO"


def test_repo_tokens_missing_or_empty_doesnt_break(monkeypatch):
    """A user who hasn't migrated yet has no repo_tokens key — must still work."""
    monkeypatch.delenv("BITBUCKET_REPO_TOKEN", raising=False)
    cfg = _cfg(repo_token="GLOBAL")  # no repo_tokens at all
    h = get_bitbucket_auth_headers(config=cfg, repo="citemed/anything")
    assert h["Authorization"] == "Bearer GLOBAL"


# ── default_repo resolution ────────────────────────────────────────────


def test_get_default_repo_env_priority(monkeypatch):
    monkeypatch.setenv("BITBUCKET_DEFAULT_REPO", "citemed/from-env")
    cfg = _cfg(default_repo="citemed/from-config")
    assert get_default_repo(config=cfg) == "citemed/from-env"


def test_get_default_repo_config_fallback(monkeypatch):
    monkeypatch.delenv("BITBUCKET_DEFAULT_REPO", raising=False)
    cfg = _cfg(default_repo="citemed/from-config")
    assert get_default_repo(config=cfg) == "citemed/from-config"


def test_get_default_repo_none_when_unset(monkeypatch):
    monkeypatch.delenv("BITBUCKET_DEFAULT_REPO", raising=False)
    cfg = _cfg()
    assert get_default_repo(config=cfg) is None


# ── _slug_from_endpoint() ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "endpoint,expected",
    [
        ("/repositories/citemed/citemed_web/pullrequests", "citemed/citemed_web"),
        ("/repositories/ws/repo/pipelines/123/steps", "ws/repo"),
        ("/repositories/ws/repo", "ws/repo"),
        ("/user", None),
        ("/repositories/ws", None),
        ("/2.0/repositories/ws/repo", None),  # we strip the API version elsewhere
        ("/workspaces/citemed", None),
    ],
)
def test_slug_from_endpoint(endpoint: str, expected):
    assert _slug_from_endpoint(endpoint) == expected
