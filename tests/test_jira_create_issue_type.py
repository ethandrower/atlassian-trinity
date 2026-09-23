"""
`jira create --type` accepts whatever the project defines, and refuses what it doesn't.

No credentials needed: the project's issue types and the create call are both stubbed,
so this asserts the CLI's own behaviour rather than Jira's.
"""

from click.testing import CliRunner

import trinity.cli as cli
import trinity.jira.create_issue as create_issue

ECD_TYPES = ["Task", "Story", "Bug", "Epic", "Incident", "Sub-task"]


def _stub(monkeypatch, types=ECD_TYPES):
    """Stub the project's types and capture what create would have been asked for."""
    sent = {}

    def fake_resolve(requested, project_key):
        for name in types:
            if name.lower() == requested.lower():
                return name, types
        return types[0], types  # the silent-substitution path

    def fake_create(**kwargs):
        sent.update(kwargs)
        return {"key": "ECD-1234", "url": "https://citemed.atlassian.net/browse/ECD-1234"}

    monkeypatch.setattr(create_issue, "resolve_issue_type", fake_resolve)
    monkeypatch.setattr(create_issue, "create_jira_issue", fake_create)
    return sent


def test_a_project_defined_type_is_accepted(monkeypatch):
    sent = _stub(monkeypatch)
    result = CliRunner().invoke(cli.cli, ["jira", "create", "--project", "ECD",
                                          "--summary", "queues-prod: ai=stale", "--type", "Incident"])
    assert result.exit_code == 0, result.output
    assert sent["issue_type"] == "Incident"
    assert "ECD-1234" in result.output


def test_an_unknown_type_fails_instead_of_creating_the_wrong_thing(monkeypatch):
    """Asking for Incident and silently getting a Task is worse than an error."""
    sent = _stub(monkeypatch, types=["Task", "Story"])
    result = CliRunner().invoke(cli.cli, ["jira", "create", "--project", "SUP",
                                          "--summary", "x", "--type", "Incident"])
    assert result.exit_code != 0
    assert "no issue type 'Incident'" in result.output
    assert "Task, Story" in result.output  # says what it could have been
    assert sent == {}  # nothing was created


def test_the_default_is_still_task(monkeypatch):
    sent = _stub(monkeypatch)
    result = CliRunner().invoke(cli.cli, ["jira", "create", "--project", "ECD", "--summary", "x"])
    assert result.exit_code == 0, result.output
    assert sent["issue_type"] == "Task"
