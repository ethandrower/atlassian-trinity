"""Search must expose the parent epic, the way get_issue already does.

Unit tests against a stubbed HTTP layer — no credentials, no network. The point is
the field mapping, which is observable without either.
"""

import pytest

from trinity.jira import search as search_mod


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _issue(key, parent=None):
    fields = {
        "summary": f"summary for {key}",
        "status": {"name": "Ready For Development"},
        "issuetype": {"name": "Story"},
    }
    if parent:
        fields["parent"] = {"key": parent, "fields": {"summary": f"epic {parent}"}}
    return {"key": key, "id": "1", "fields": fields}


@pytest.fixture
def captured(monkeypatch):
    """Capture the outgoing payload and return a canned Jira response."""
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["payload"] = json
        return FakeResponse(
            {"total": 2, "issues": [_issue("ECD-2299", "ECD-2298"), _issue("ECD-1359")]}
        )

    monkeypatch.setattr(search_mod.requests, "post", fake_post)
    monkeypatch.setattr(search_mod, "get_jira_auth_headers", lambda: {})
    return seen


def test_parent_is_requested(captured):
    """Jira omits parent unless asked, so the field list must include it."""
    search_mod.search_jira("project = ECD")
    assert "parent" in captured["payload"]["fields"]


def test_epic_key_is_mapped(captured):
    result = search_mod.search_jira("project = ECD")
    by_key = {i["key"]: i for i in result["issues"]}
    assert by_key["ECD-2299"]["epic_key"] == "ECD-2298"
    assert by_key["ECD-2299"]["epic_summary"] == "epic ECD-2298"


def test_issue_without_parent_is_none_not_missing(captured):
    """Callers check truthiness; a missing key would raise instead."""
    result = search_mod.search_jira("project = ECD")
    by_key = {i["key"]: i for i in result["issues"]}
    assert by_key["ECD-1359"]["epic_key"] is None
    assert by_key["ECD-1359"]["epic_summary"] is None


def test_explicit_fields_are_respected(captured):
    """An explicit --fields list must not be silently overridden."""
    search_mod.search_jira("project = ECD", fields=["summary"])
    assert captured["payload"]["fields"] == ["summary"]
