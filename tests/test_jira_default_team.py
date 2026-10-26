"""`jira create` puts the project's default Team on every issue it makes.

Agents create most tickets, and an ECD ticket with no Team (customfield_10001)
drops off the ECD team's boards. jira.default_team in config maps project key ->
Atlassian team id; --team overrides it, --no-team skips it. Offline: the HTTP
call is captured, never sent.
"""

from types import SimpleNamespace

import pytest

from trinity.base import auth
from trinity.jira import create_issue as ci

ECD_TEAM = "61639349-d3f9-4cd1-9bfd-611f9fa7686d"


@pytest.fixture
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(ci, "resolve_issue_type", lambda t, p: (t, [t]))
    monkeypatch.setattr(ci, "get_jira_auth_headers", lambda: {})
    monkeypatch.setattr(auth, "load_config", lambda: {"jira": {"default_team": {"ECD": ECD_TEAM}}})

    def post(url, headers=None, json=None, timeout=None):
        calls.append(json["fields"])
        return SimpleNamespace(status_code=201, json=lambda: {"key": "ECD-1", "id": "1"}, text="")

    monkeypatch.setattr(ci.requests, "post", post)
    return calls


def test_default_team_applied(sent):
    ci.create_jira_issue("ECD", "s")
    assert sent[0][ci.TEAM_FIELD] == ECD_TEAM


def test_explicit_team_wins(sent):
    ci.create_jira_issue("ECD", "s", team_id="other-team")
    assert sent[0][ci.TEAM_FIELD] == "other-team"


def test_no_team_skips_default(sent):
    ci.create_jira_issue("ECD", "s", use_default_team=False)
    assert ci.TEAM_FIELD not in sent[0]


def test_project_without_default_gets_no_team(sent):
    ci.create_jira_issue("GO", "s")
    assert ci.TEAM_FIELD not in sent[0]
