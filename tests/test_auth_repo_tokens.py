"""Per-repo Bitbucket tokens must count as configured credentials.

Regression cover for a gate that rejected every ``bb`` command on a machine
credentialed entirely with per-repo tokens. ``is_authenticated("bitbucket")``
asked ``get_bitbucket_auth_headers()`` with no repo slug, which skips the
``repo_tokens`` map by design, so the answer was False while the resolver
would have served each individual command correctly a moment later.

These tests build their config in-process rather than reading the developer's
real ~/.trinity/config.yaml, so they assert the logic on any machine --
including CI, where no credentials exist at all.
"""

import pytest

from trinity.base import auth
from trinity.base.exceptions import AuthenticationError

BB_ENV = (
    "BITBUCKET_REPO_TOKEN",
    "BITBUCKET_USERNAME",
    "BITBUCKET_APP_PASSWORD",
)


@pytest.fixture
def no_bb_env(monkeypatch):
    """Bitbucket env vars outrank the config file; clear them."""
    for name in BB_ENV:
        monkeypatch.delenv(name, raising=False)


def _config(**bitbucket):
    return {"atlassian": {}, "bitbucket": bitbucket, "api": {}}


def _with_config(monkeypatch, cfg):
    monkeypatch.setattr(auth, "load_config", lambda: cfg)


PER_REPO_ONLY = {"repo_tokens": {"citemed/citemed_web": "tok-web"}}


def test_per_repo_token_alone_counts_as_authenticated(monkeypatch, no_bb_env):
    """The regression: no global token, only a per-repo map."""
    _with_config(monkeypatch, _config(**PER_REPO_ONLY))
    assert auth.is_authenticated("bitbucket") is True


def test_authenticated_for_a_specific_repo(monkeypatch, no_bb_env):
    _with_config(monkeypatch, _config(**PER_REPO_ONLY))
    assert auth.is_authenticated("bitbucket", repo="citemed/citemed_web") is True


def test_per_repo_token_is_the_one_sent(monkeypatch, no_bb_env):
    _with_config(monkeypatch, _config(**PER_REPO_ONLY))
    headers = auth.get_bitbucket_auth_headers(repo="citemed/citemed_web")
    assert headers["Authorization"] == "Bearer tok-web"


def test_per_repo_token_beats_global(monkeypatch, no_bb_env):
    """Repo tokens are narrower, so they win where both could apply."""
    _with_config(
        monkeypatch,
        _config(repo_token="tok-global", repo_tokens={"citemed/citemed_web": "tok-web"}),
    )
    assert (
        auth.get_bitbucket_auth_headers(repo="citemed/citemed_web")["Authorization"]
        == "Bearer tok-web"
    )
    # A repo with no entry of its own still falls back to the global token.
    assert (
        auth.get_bitbucket_auth_headers(repo="citemed/other")["Authorization"]
        == "Bearer tok-global"
    )


def test_no_credentials_at_all_is_unauthenticated(monkeypatch, no_bb_env):
    _with_config(monkeypatch, _config(repo_tokens={}))
    assert auth.is_authenticated("bitbucket") is False


def test_empty_repo_token_map_does_not_count(monkeypatch, no_bb_env):
    """Guard the fallback against a config file carrying the key but no values."""
    _with_config(monkeypatch, _config(repo_tokens=None))
    assert auth.is_authenticated("bitbucket") is False


def test_error_for_uncredentialed_repo_names_it(monkeypatch, no_bb_env):
    """'Credentials for other repos, none for this one' is the common case."""
    _with_config(monkeypatch, _config(**PER_REPO_ONLY))
    with pytest.raises(AuthenticationError) as excinfo:
        auth.get_bitbucket_auth_headers(repo="citemed/unknown")
    message = str(excinfo.value)
    assert "citemed/unknown" in message
    assert "--bb-repo-token" in message
