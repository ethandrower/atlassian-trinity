"""Reviewer support: create/update --reviewer, `bb ready`, aliases, config.

Pure unit tests in the style of test_bb_draft_pr.py: the HTTP layer is stubbed,
so the request payloads are asserted and nothing touches Bitbucket.
"""

import json

import pytest
from click.testing import CliRunner

from trinity.base.exceptions import TrinityError
from trinity.bitbucket.api import BitbucketAPI
from trinity.bitbucket.commands import create_pr, ready_pr, update_pr
from trinity.bitbucket.reviewers import ReviewerResolver, merge_reviewers

DEVBOT = "{55a6c1a9-f436-4f0a-b5ec-6254ab128261}"
JOSHUA = "{11da5d04-3269-4550-be32-e201addc45af}"
MOHAMED = "{083dc6c7-e8a6-4cad-825f-8e39e5b97e9b}"
DZANA = "{fca21542-39d4-4c57-a4eb-2cd8b2c6b5ea}"
ETHAN = "{00000000-0000-4000-8000-000000000001}"
OTHER = "{00000000-0000-4000-8000-000000000002}"

CFG = {
    "bitbucket": {
        "default_reviewers": [DEVBOT, "joshua", "mohamed"],
        "pm_reviewers": ["dzana"],
        "reviewer_aliases": {"devbot": DEVBOT, "joshua": JOSHUA,
                             "Mohamed": MOHAMED, "dzana": DZANA},
    }
}


class FakeAPI(BitbucketAPI):
    """Holds one PR in memory and records every write."""

    def __init__(self, pr=None, me=ETHAN, members=()):  # noqa: D107 - skips auth
        self.pr = pr or {}
        self.me = me
        self.members = list(members)
        self.posts = []
        self.puts = []

    def get(self, endpoint, params=None):
        if endpoint == "/user":
            return {"uuid": self.me}
        if "/pullrequests/" in endpoint:
            return json.loads(json.dumps(self.pr))
        raise AssertionError(f"unexpected GET {endpoint}")

    def get_all_pages(self, endpoint, params=None, max_items=None):
        if endpoint.endswith("/members"):
            return [{"user": u} for u in self.members]
        return []

    def post(self, endpoint, json=None):
        self.posts.append(json)
        return {"id": 7, "reviewers": json.get("reviewers", []), "links": {}}

    def put(self, endpoint, json=None):
        self.puts.append(json)
        self.pr.update(json)
        self.pr["reviewers"] = [{"uuid": r["uuid"], "display_name": r["uuid"]}
                                for r in self.pr.get("reviewers", [])]
        return json_copy(self.pr)


def json_copy(d):
    return json.loads(json.dumps(d))


def _pr(draft=True, reviewers=(), author=ETHAN):
    return {
        "id": 42, "title": "Keep me", "description": "Body stays",
        "state": "OPEN", "draft": draft,
        "author": {"uuid": author, "display_name": "Ethan"},
        "reviewers": [{"uuid": u} for u in reviewers],
        "links": {"html": {"href": "https://bitbucket.org/ws/repo/pull-requests/42"}},
    }


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setattr("trinity.bitbucket.reviewers.load_config", lambda: CFG)


def _uuids(payload):
    return [r["uuid"] for r in payload["reviewers"]]


# ── create ────────────────────────────────────────────────────────────────────

def test_create_adds_reviewers_by_uuid_and_alias():
    api = FakeAPI()
    create_pr(api, "ws", "repo", title="t", source="f", dest="develop",
              reviewers=[DEVBOT, "joshua"])
    assert _uuids(api.posts[0]) == [DEVBOT, JOSHUA]


def test_create_accepts_the_old_comma_string():
    api = FakeAPI()
    create_pr(api, "ws", "repo", title="t", source="f", reviewers="devbot, mohamed")
    assert _uuids(api.posts[0]) == [DEVBOT, MOHAMED]


def test_create_skips_the_author():
    api = FakeAPI(me=DEVBOT)
    create_pr(api, "ws", "repo", title="t", source="f", reviewers=["devbot", "joshua"])
    assert _uuids(api.posts[0]) == [JOSHUA]


def test_create_without_reviewers_sends_none():
    api = FakeAPI()
    create_pr(api, "ws", "repo", title="t", source="f")
    assert "reviewers" not in api.posts[0]


# ── update ────────────────────────────────────────────────────────────────────

def test_update_adds_without_dropping_existing():
    api = FakeAPI(pr=_pr(draft=False, reviewers=[OTHER]))
    update_pr(api, "ws", "repo", 42, add_reviewers=["dzana"])
    put = api.puts[0]
    assert _uuids(put) == [OTHER, DZANA]
    assert put["title"] == "Keep me" and put["description"] == "Body stays"
    assert "draft" not in put


def test_update_removes_a_reviewer():
    api = FakeAPI(pr=_pr(draft=False, reviewers=[OTHER, JOSHUA]))
    update_pr(api, "ws", "repo", 42, remove_reviewers=["joshua"])
    assert _uuids(api.puts[0]) == [OTHER]


def test_update_title_only_leaves_reviewers_alone():
    api = FakeAPI(pr=_pr(reviewers=[OTHER]))
    update_pr(api, "ws", "repo", 42, title="New")
    assert api.puts[0] == {"title": "New"}


# ── ready ─────────────────────────────────────────────────────────────────────

def test_ready_flips_draft_and_adds_defaults_in_one_put():
    api = FakeAPI(pr=_pr(draft=True))
    result = ready_pr(api, "ws", "repo", 42, cfg=CFG)
    assert len(api.puts) == 1
    put = api.puts[0]
    assert put["draft"] is False
    assert put["title"] == "Keep me" and put["description"] == "Body stays"
    assert _uuids(put) == [DEVBOT, JOSHUA, MOHAMED]
    assert result["draft"] is False and result["changed"] is True


def test_ready_preserves_existing_reviewers():
    api = FakeAPI(pr=_pr(reviewers=[OTHER, JOSHUA]))
    ready_pr(api, "ws", "repo", 42, cfg=CFG)
    assert _uuids(api.puts[0]) == [OTHER, JOSHUA, DEVBOT, MOHAMED]


def test_ready_skips_the_author():
    api = FakeAPI(pr=_pr(author=MOHAMED))
    result = ready_pr(api, "ws", "repo", 42, cfg=CFG)
    assert MOHAMED not in _uuids(api.puts[0])
    assert result["skipped_author"] == [MOHAMED]


def test_ready_adds_pm_only_when_client_visible():
    api = FakeAPI(pr=_pr())
    ready_pr(api, "ws", "repo", 42, cfg=CFG)
    assert DZANA not in _uuids(api.puts[0])

    api = FakeAPI(pr=_pr())
    ready_pr(api, "ws", "repo", 42, client_visible=True, cfg=CFG)
    assert _uuids(api.puts[0])[-1] == DZANA


# The migrated tier model: Mohamed sits in cto_reviewers, dropped by --simple.
CFG_CTO = {
    "bitbucket": {
        "default_reviewers": [DEVBOT, "joshua"],
        "cto_reviewers": ["mohamed"],
        "pm_reviewers": ["dzana"],
        "reviewer_aliases": {"devbot": DEVBOT, "joshua": JOSHUA,
                             "mohamed": MOHAMED, "dzana": DZANA},
    }
}


def test_ready_adds_cto_tier_by_default():
    api = FakeAPI(pr=_pr())
    ready_pr(api, "ws", "repo", 42, cfg=CFG_CTO)
    assert _uuids(api.puts[0]) == [DEVBOT, JOSHUA, MOHAMED]


def test_ready_simple_drops_the_cto_tier():
    api = FakeAPI(pr=_pr())
    ready_pr(api, "ws", "repo", 42, simple=True, cfg=CFG_CTO)
    assert _uuids(api.puts[0]) == [DEVBOT, JOSHUA]


def test_ready_simple_still_adds_pm_when_client_visible():
    api = FakeAPI(pr=_pr())
    ready_pr(api, "ws", "repo", 42, simple=True, client_visible=True, cfg=CFG_CTO)
    uuids = _uuids(api.puts[0])
    assert MOHAMED not in uuids and DZANA in uuids


def test_ready_no_defaults_with_explicit_reviewer():
    api = FakeAPI(pr=_pr())
    ready_pr(api, "ws", "repo", 42, use_defaults=False, reviewers=["dzana"], cfg=CFG)
    assert _uuids(api.puts[0]) == [DZANA]


def test_ready_is_idempotent():
    api = FakeAPI(pr=_pr())
    ready_pr(api, "ws", "repo", 42, cfg=CFG)
    second = ready_pr(api, "ws", "repo", 42, cfg=CFG)
    assert len(api.puts) == 1
    assert second["changed"] is False and second["draft"] is False


def test_ready_on_non_draft_pr_still_adds_missing_reviewers():
    api = FakeAPI(pr=_pr(draft=False, reviewers=[DEVBOT]))
    result = ready_pr(api, "ws", "repo", 42, cfg=CFG)
    assert result["changed"] is True
    assert _uuids(api.puts[0]) == [DEVBOT, JOSHUA, MOHAMED]


# ── resolution ────────────────────────────────────────────────────────────────

def test_aliases_are_case_insensitive_and_uuids_normalised():
    r = ReviewerResolver(FakeAPI(), "ws", "repo", cfg=CFG)
    assert r.resolve("MOHAMED") == MOHAMED
    assert r.resolve(DEVBOT.strip("{}").upper()) == DEVBOT


def test_nickname_resolves_through_workspace_members():
    api = FakeAPI(members=[{"nickname": "jmulei", "uuid": JOSHUA}])
    assert ReviewerResolver(api, "ws", "repo", cfg=CFG).resolve("jmulei") == JOSHUA


def test_unknown_reviewer_is_a_clear_error():
    with pytest.raises(TrinityError, match="bb-reviewer-alias"):
        ReviewerResolver(FakeAPI(), "ws", "repo", cfg=CFG).resolve("nobody")


def test_merge_dedupes():
    merged, summary = merge_reviewers([{"uuid": DEVBOT}], add=[DEVBOT, JOSHUA, JOSHUA])
    assert [m["uuid"] for m in merged] == [DEVBOT, JOSHUA]
    assert summary["added"] == [JOSHUA]


# ── CLI wiring ────────────────────────────────────────────────────────────────

def test_cli_flags_exist():
    from trinity.cli import cli
    runner = CliRunner()
    assert "--reviewer" in runner.invoke(cli, ["bb", "create", "--help"]).output
    out = runner.invoke(cli, ["bb", "update", "--help"]).output
    assert "--reviewer" in out and "--remove-reviewer" in out
    out = runner.invoke(cli, ["bb", "ready", "--help"]).output
    assert "--client-visible" in out and "--no-default-reviewers" in out


def test_cli_ready_json(monkeypatch):
    from trinity import cli as cli_mod
    api = FakeAPI(pr=_pr())
    monkeypatch.setattr("trinity.bitbucket.api.BitbucketAPI", lambda: api)
    monkeypatch.setattr(cli_mod, "_bb_context", lambda ctx: ("ws", "repo"))
    result = CliRunner().invoke(cli_mod.cli, ["--json", "bb", "ready", "42", "--client-visible"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["draft"] is False
    assert [r["uuid"] for r in data["reviewers"]] == [DEVBOT, JOSHUA, MOHAMED, DZANA]


def test_config_reviewer_flags(monkeypatch):
    from trinity import cli as cli_mod
    saved = {}
    cfg = {"atlassian": {}, "bitbucket": {"default_reviewers": [DEVBOT]}}
    monkeypatch.setattr("trinity.base.auth.load_config", lambda: cfg)
    monkeypatch.setattr("trinity.base.auth.save_config", lambda c: saved.update(c))
    result = CliRunner().invoke(cli_mod.cli, [
        "config", "--bb-default-reviewer", JOSHUA, "--bb-default-reviewer", DEVBOT,
        "--bb-pm-reviewer", "dzana", "--bb-reviewer-alias", f"Dzana={DZANA}",
    ])
    assert result.exit_code == 0, result.output
    bb = saved["bitbucket"]
    assert bb["default_reviewers"] == [DEVBOT, JOSHUA]
    assert bb["pm_reviewers"] == ["dzana"]
    assert bb["reviewer_aliases"] == {"dzana": DZANA}
