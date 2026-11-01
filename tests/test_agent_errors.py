"""
Failures have to say what actually went wrong, because agents act on the words.

A rejected Jira login used to read as "issue does not exist" or as an empty
search, and a missing repo read as a bad token. An agent believes those answers
and goes off chasing the wrong problem.
"""

import json
import sys

import pytest
import requests
from click.testing import CliRunner

from trinity import cli
from trinity.base import health
from trinity.base.exceptions import AuthenticationError, NotFoundError
from trinity.bitbucket import api as bb_api


@pytest.fixture(autouse=True)
def _no_login_check():
    """Override conftest's stub: these tests exercise the real check."""


class _Response:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


@pytest.fixture
def jira_answers(monkeypatch):
    monkeypatch.setenv("ATLASSIAN_EMAIL", "someone@example.com")
    monkeypatch.setenv("ATLASSIAN_API_TOKEN", "token")
    monkeypatch.setenv("ATLASSIAN_JIRA_URL", "https://example.atlassian.net")

    def answer(result):
        def fake_get(*args, **kwargs):
            if isinstance(result, Exception):
                raise result
            return result
        monkeypatch.setattr(health.requests, "get", fake_get)

    return answer


def test_rejected_login_stops_the_command_before_it_runs(jira_answers, monkeypatch):
    jira_answers(_Response(401))
    ran = []
    monkeypatch.setattr("trinity.jira.search.search_jira", lambda *a: ran.append(1))

    result = CliRunner().invoke(cli.cli, ["jira", "search", "project = ECD"])

    assert isinstance(result.exception, AuthenticationError)
    assert "someone@example.com" in str(result.exception)
    assert ran == []


def test_good_login_lets_the_command_run(jira_answers, monkeypatch):
    jira_answers(_Response(200))
    monkeypatch.setattr("trinity.jira.search.search_jira",
                        lambda *a: {"total": 0, "count": 0, "issues": []})

    result = CliRunner().invoke(cli.cli, ["jira", "search", "project = ECD"])

    assert result.exit_code == 0, result.output


def test_network_failure_does_not_block_the_command(jira_answers):
    jira_answers(requests.ConnectionError("no route"))

    health.require_atlassian_login()


def test_help_needs_no_login(jira_answers):
    jira_answers(_Response(401))

    result = CliRunner().invoke(cli.cli, ["jira", "search", "--help"])

    assert result.exit_code == 0
    assert "Examples:" in result.output


def test_doctor_reports_each_check_and_fails_when_one_does(jira_answers, monkeypatch):
    jira_answers(_Response(401))
    monkeypatch.setattr(health, "load_config", lambda: {
        "atlassian": {}, "bitbucket": {"repo_tokens": {"acme/web": "x"}},
    })
    monkeypatch.setattr(health, "resolve_workspace_repo", lambda *a: ("", ""))
    monkeypatch.setattr(bb_api.BitbucketAPI, "get", lambda self, endpoint: {})

    result = CliRunner().invoke(cli.cli, ["doctor", "--json"])

    report = json.loads(result.output)
    assert result.exit_code == 1
    assert report["ok"] is False
    assert [c["ok"] for c in report["checks"]] == [False, True]
    assert report["checks"][1]["check"] == "Bitbucket acme/web"


@pytest.mark.parametrize("args", [
    ["--json", "doctor"],
    ["doctor", "--json"],
])
def test_json_flag_works_either_side_of_the_subcommand(args, monkeypatch):
    monkeypatch.setattr(health, "run_checks",
                        lambda: {"ok": True, "config_file": "x", "checks": []})

    result = CliRunner().invoke(cli.cli, args)

    assert json.loads(result.output)["ok"] is True


def test_table_flag_overrides_piped_json(monkeypatch):
    monkeypatch.setattr(health, "run_checks",
                        lambda: {"ok": True, "config_file": "x", "checks": []})

    result = CliRunner().invoke(cli.cli, ["doctor", "--table"])

    assert result.exit_code == 0
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.output)


def test_text_after_a_double_dash_is_left_alone(jira_answers, monkeypatch):
    jira_answers(_Response(200))
    sent = []
    monkeypatch.setattr("trinity.jira.add_comment.add_jira_comment",
                        lambda key, text, mentions: sent.append(text) or {})

    CliRunner().invoke(cli.cli, ["jira", "comment", "--", "ECD-1", "--json"])

    assert sent == ["--json"]


def test_piped_output_defaults_to_json(monkeypatch):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False, raising=False)
    assert cli._wants_json() is True

    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    assert cli._wants_json() is False
    assert cli._wants_json(True) is True


def test_errors_are_clean_json_when_piped(monkeypatch, capsys):
    def boom(*a, **k):
        raise NotFoundError("Resource not found.")

    monkeypatch.setattr(cli, "cli", boom)
    monkeypatch.setattr(sys, "argv", ["trinity", "--json", "bb", "show", "1"])

    with pytest.raises(SystemExit) as e:
        cli.main()

    assert e.value.code == 1
    assert json.loads(capsys.readouterr().out) == {
        "error": True, "error_type": "NotFoundError", "message": "Resource not found.",
    }


def test_rejected_repo_token_says_which_token_and_how_to_replace_it(monkeypatch):
    monkeypatch.setattr(bb_api, "load_config",
                        lambda: {"bitbucket": {"repo_tokens": {"acme/web": "x"}}})

    known = bb_api._rejected_token_message("acme/web")
    unknown = bb_api._rejected_token_message("acme/typo")

    assert "--bb-repo-token acme/web=NEW_TOKEN" in known
    assert "no token of its own" in unknown
    assert "acme/web" in unknown
