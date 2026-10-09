"""Offline tests for BitbucketAPI call paths that bypass _request."""

from types import SimpleNamespace

from trinity.bitbucket.api import BitbucketAPI


def test_step_log_sends_the_per_repo_token(monkeypatch):
    """get_step_log builds its own request, so it must pass the repo slug too."""
    api = BitbucketAPI()
    seen = {}
    monkeypatch.setattr(api, "_headers", lambda repo=None: seen.setdefault("repo", repo) and {})
    monkeypatch.setattr(
        api.session, "get",
        lambda url, **kw: SimpleNamespace(status_code=200, text="log line", headers={}),
    )
    assert api.get_step_log("citemed", "citemed_web", "{p}", "{s}") == "log line"
    assert seen["repo"] == "citemed/citemed_web"


def test_diff_sends_the_per_repo_token(monkeypatch):
    """get_diff builds its own request too; without the slug it fell back to the
    global token and failed for anyone credentialed with per-repo tokens."""
    api = BitbucketAPI()
    seen = {}
    monkeypatch.setattr(api, "_headers", lambda repo=None: seen.setdefault("repo", repo) and {} or {})
    monkeypatch.setattr(
        api.session, "get",
        lambda url, **kw: SimpleNamespace(status_code=200, text="diff --git a b", headers={}),
    )
    assert api.get_diff("citemed", "citemed_web", 1) == "diff --git a b"
    assert seen["repo"] == "citemed/citemed_web"


def _fake_pages(api, monkeypatch, total):
    calls = []

    def get(endpoint, params=None):
        calls.append(params)
        page = len(calls)
        size = (params or {}).get("pagelen", 50) if page == 1 else 50
        start = (page - 1) * 50
        values = [{"id": i} for i in range(start, min(start + size, total))]
        nxt = f"{api.base_url}/next?page={page + 1}" if start + size < total else None
        return {"values": values, "next": nxt}

    monkeypatch.setattr(api, "get", get)
    return calls


def test_pr_limit_above_50_is_capped_and_paged(monkeypatch):
    api = BitbucketAPI()
    calls = _fake_pages(api, monkeypatch, total=120)
    prs = api.list_pull_requests("citemed", "citemed_web", state="OPEN", limit=100)
    assert calls[0]["pagelen"] == 50
    assert len(prs) == 100


def test_pr_limit_at_or_below_50_is_one_page(monkeypatch):
    api = BitbucketAPI()
    calls = _fake_pages(api, monkeypatch, total=120)
    prs = api.list_pull_requests("citemed", "citemed_web", state="OPEN", limit=20)
    assert calls == [{"state": "OPEN", "pagelen": 20}]
    assert len(prs) == 20
