"""Approving a PR must act as a real Bitbucket user, not a repo access token.

Bitbucket repository/workspace access tokens cannot approve or decline pull
requests — the /approve endpoint returns HTTP 400 for them, because approval is
recorded against a user account. These tests cover the user-auth resolver and
the ``--as`` identity mechanism that let ``trinity bb approve`` act as a user
(e.g. devbot) regardless of what token the home is otherwise configured with.

Config is built in-process, so these assert the logic on any machine (CI
included) without reading the developer's real ~/.trinity/config.yaml.
"""

import base64

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
    for name in BB_ENV:
        monkeypatch.delenv(name, raising=False)


def _config(**bitbucket):
    return {"atlassian": {}, "bitbucket": bitbucket, "api": {}}


def _with_config(monkeypatch, cfg):
    monkeypatch.setattr(auth, "load_config", lambda: cfg)


def _decode_basic(headers):
    scheme, _, b64 = headers["Authorization"].partition(" ")
    assert scheme == "Basic"
    return base64.b64decode(b64).decode()


# ── user credential detection ────────────────────────────────────────────────

def test_has_user_credentials_from_config(monkeypatch, no_bb_env):
    cfg = _config(username="devbot@citemed.com", app_password="pw")
    assert auth.has_bitbucket_user_credentials(cfg) is True


def test_has_user_credentials_false_for_token_only(monkeypatch, no_bb_env):
    cfg = _config(repo_token="ATCTtoken")
    assert auth.has_bitbucket_user_credentials(cfg) is False


# ── get_bitbucket_user_auth_headers ──────────────────────────────────────────

def test_user_headers_from_current_home(monkeypatch, no_bb_env):
    cfg = _config(username="devbot@citemed.com", app_password="secret")
    assert _decode_basic(
        auth.get_bitbucket_user_auth_headers(config=cfg)
    ) == "devbot@citemed.com:secret"


def test_user_headers_never_use_a_repo_token(monkeypatch, no_bb_env):
    """A token on file must not be used for a user-only action."""
    cfg = _config(repo_token="ATCTtoken", repo_tokens={"citemed/web": "ATCTweb"})
    with pytest.raises(AuthenticationError) as excinfo:
        auth.get_bitbucket_user_auth_headers(config=cfg, repo="citemed/web")
    msg = str(excinfo.value)
    assert "cannot approve" in msg.lower()


def test_actionable_error_suggests_as_flag(monkeypatch, no_bb_env):
    cfg = _config(repo_token="ATCTtoken",
                  identities={"devbot": {"home": "~/.trinity-agent"}})
    with pytest.raises(AuthenticationError) as excinfo:
        auth.get_bitbucket_user_auth_headers(config=cfg)
    assert "--as" in str(excinfo.value)
    assert "devbot" in str(excinfo.value)


# ── named identities (--as) ──────────────────────────────────────────────────

def test_identity_inline_credentials(monkeypatch, no_bb_env):
    cfg = _config(
        repo_token="ATCTtoken",
        identities={"bot": {"username": "bot@x.com", "app_password": "p"}},
    )
    headers = auth.get_bitbucket_user_auth_headers(config=cfg, as_identity="bot")
    assert _decode_basic(headers) == "bot@x.com:p"


def test_identity_reads_another_home(monkeypatch, no_bb_env, tmp_path):
    home = tmp_path / "agent"
    home.mkdir()
    (home / "config.yaml").write_text(
        "bitbucket:\n  username: devbot@citemed.com\n  app_password: homesecret\n"
    )
    cfg = _config(repo_token="ATCTtoken",
                  identities={"devbot": {"home": str(home)}})
    headers = auth.get_bitbucket_user_auth_headers(config=cfg, as_identity="devbot")
    assert _decode_basic(headers) == "devbot@citemed.com:homesecret"


def test_identity_home_may_be_a_bare_string(monkeypatch, no_bb_env, tmp_path):
    home = tmp_path / "agent"
    home.mkdir()
    (home / "config.yaml").write_text(
        "bitbucket:\n  username: u\n  app_password: p\n"
    )
    cfg = _config(identities={"devbot": str(home)})
    headers = auth.get_bitbucket_user_auth_headers(config=cfg, as_identity="devbot")
    assert _decode_basic(headers) == "u:p"


def test_identity_wins_over_repo_token_env(monkeypatch):
    """An explicit --as identity is immune to a BITBUCKET_REPO_TOKEN override."""
    monkeypatch.setenv("BITBUCKET_REPO_TOKEN", "ATCTfromenv")
    monkeypatch.delenv("BITBUCKET_USERNAME", raising=False)
    monkeypatch.delenv("BITBUCKET_APP_PASSWORD", raising=False)
    cfg = _config(identities={"bot": {"username": "bot@x.com", "app_password": "p"}})
    headers = auth.get_bitbucket_user_auth_headers(config=cfg, as_identity="bot")
    assert _decode_basic(headers) == "bot@x.com:p"


def test_unknown_identity_lists_configured(monkeypatch, no_bb_env):
    cfg = _config(identities={"devbot": {"home": "~/.trinity-agent"}})
    with pytest.raises(AuthenticationError) as excinfo:
        auth.get_bitbucket_user_auth_headers(config=cfg, as_identity="nope")
    msg = str(excinfo.value)
    assert "nope" in msg and "devbot" in msg


def test_identity_without_usable_credentials(monkeypatch, no_bb_env, tmp_path):
    home = tmp_path / "agent"
    home.mkdir()
    (home / "config.yaml").write_text("bitbucket:\n  repo_token: ATCTonly\n")
    cfg = _config(identities={"devbot": {"home": str(home)}})
    with pytest.raises(AuthenticationError):
        auth.get_bitbucket_user_auth_headers(config=cfg, as_identity="devbot")


# ── BitbucketAPI auth routing ────────────────────────────────────────────────

def test_api_require_user_routes_to_user_auth(monkeypatch, no_bb_env):
    from trinity.bitbucket.api import BitbucketAPI
    cfg = _config(username="devbot@citemed.com", app_password="secret")
    _with_config(monkeypatch, cfg)
    api = BitbucketAPI(require_user=True)
    assert _decode_basic(api._headers(repo="citemed/web")) == "devbot@citemed.com:secret"


def test_api_default_still_uses_token(monkeypatch, no_bb_env):
    from trinity.bitbucket.api import BitbucketAPI
    cfg = _config(repo_tokens={"citemed/web": "ATCTweb"})
    _with_config(monkeypatch, cfg)
    api = BitbucketAPI()
    assert api._headers(repo="citemed/web")["Authorization"] == "Bearer ATCTweb"


def test_api_prefer_user_falls_back_to_token(monkeypatch, no_bb_env):
    from trinity.bitbucket.api import BitbucketAPI
    cfg = _config(repo_tokens={"citemed/web": "ATCTweb"})
    _with_config(monkeypatch, cfg)
    api = BitbucketAPI(prefer_user=True)
    # No user creds configured, so decline still works via the token.
    assert api._headers(repo="citemed/web")["Authorization"] == "Bearer ATCTweb"


# ── CLI wiring ───────────────────────────────────────────────────────────────

class _CaptureAPI:
    """Stands in for BitbucketAPI, recording how the CLI constructed it."""

    last_kwargs: dict = {}

    def __init__(self, *args, **kwargs):
        _CaptureAPI.last_kwargs = kwargs

    def approve_pull_request(self, *a, **k):
        return {"approved": True}

    def decline_pull_request(self, *a, **k):
        return {"state": "DECLINED"}

    def add_comment(self, *a, **k):
        return {"id": 1}

    def request_changes_pull_request(self, *a, **k):
        return {"state": "changes_requested"}

    def remove_change_request_pull_request(self, *a, **k):
        return {}


def _run_capture(monkeypatch, argv):
    from click.testing import CliRunner
    from trinity import cli as cli_mod
    monkeypatch.setattr("trinity.bitbucket.api.BitbucketAPI", _CaptureAPI)
    monkeypatch.setattr(cli_mod, "_bb_context", lambda ctx: ("ws", "repo"))
    _CaptureAPI.last_kwargs = {}
    return CliRunner().invoke(cli_mod.cli, argv)


def test_cli_approve_as_builds_user_api(monkeypatch):
    result = _run_capture(monkeypatch, ["--json", "bb", "approve", "42", "--as", "devbot"])
    assert result.exit_code == 0, result.output
    assert _CaptureAPI.last_kwargs == {"require_user": True, "as_identity": "devbot"}


def test_cli_approve_without_as_still_requires_user(monkeypatch):
    result = _run_capture(monkeypatch, ["--json", "bb", "approve", "42"])
    assert result.exit_code == 0, result.output
    assert _CaptureAPI.last_kwargs["require_user"] is True
    assert _CaptureAPI.last_kwargs["as_identity"] is None


def test_cli_decline_prefers_user(monkeypatch):
    result = _run_capture(monkeypatch, ["--json", "bb", "decline", "42", "--as", "devbot"])
    assert result.exit_code == 0, result.output
    assert _CaptureAPI.last_kwargs == {"prefer_user": True, "as_identity": "devbot"}


def test_cli_comment_as_devbot_prefers_user(monkeypatch):
    result = _run_capture(
        monkeypatch, ["--json", "bb", "comment", "42", "-m", "hi", "--as", "devbot"]
    )
    assert result.exit_code == 0, result.output
    assert _CaptureAPI.last_kwargs == {"prefer_user": True, "as_identity": "devbot"}


def test_cli_comment_without_as_still_works(monkeypatch):
    result = _run_capture(monkeypatch, ["--json", "bb", "comment", "42", "-m", "hi"])
    assert result.exit_code == 0, result.output
    assert _CaptureAPI.last_kwargs == {"prefer_user": True, "as_identity": None}


def test_cli_request_changes_requires_user(monkeypatch):
    result = _run_capture(
        monkeypatch, ["--json", "bb", "request-changes", "42", "--as", "devbot"]
    )
    assert result.exit_code == 0, result.output
    assert _CaptureAPI.last_kwargs == {"require_user": True, "as_identity": "devbot"}
