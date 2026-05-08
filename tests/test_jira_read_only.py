"""
Live read-only Jira API smoke tests.

Each test calls a Trinity Jira function and asserts:
  1. The function returns a dict
  2. result.get("error") is not True
  3. The expected top-level fields are present

Anything that 4xx/5xx-d before the URL-family fix must now succeed here.
Tests are skipped automatically when no Atlassian creds are configured.
"""

import pytest

from trinity import jira as jira_mod

pytestmark = pytest.mark.jira_auth


def _assert_ok(result: dict, *expected_fields: str) -> None:
    assert isinstance(result, dict), f"expected dict, got {type(result).__name__}"
    assert not result.get("error"), f"API error: {result}"
    for field in expected_fields:
        assert field in result, f"missing field {field!r} in result: {list(result.keys())}"


def test_list_projects():
    result = jira_mod.list_jira_projects(max_results=5)
    _assert_ok(result, "count", "projects")
    assert result["count"] >= 0


def test_search_jql(known_project_key):
    result = jira_mod.search_jira(
        f"project = {known_project_key}", max_results=3
    )
    _assert_ok(result, "total", "count", "issues")


def test_get_issue(known_issue_key):
    result = jira_mod.get_jira_issue(known_issue_key)
    _assert_ok(result, "key", "summary", "status")
    assert result["key"] == known_issue_key


def test_get_transitions(known_issue_key):
    result = jira_mod.get_jira_transitions(known_issue_key)
    _assert_ok(result, "issue_key", "transitions")
    assert result["issue_key"] == known_issue_key


def test_get_status_history(known_issue_key):
    result = jira_mod.get_status_history(known_issue_key)
    _assert_ok(result, "issue_key", "current_status")


def test_get_worklogs(known_issue_key):
    result = jira_mod.get_issue_worklogs(known_issue_key)
    _assert_ok(result)
    # worklogs may be empty — that's still success
    assert "worklogs" in result or "total" in result or "count" in result


def test_lookup_user_self():
    """Look up the configured user — guaranteed to exist."""
    from trinity.base.auth import load_config
    import os

    email = (
        os.getenv("ATLASSIAN_EMAIL")
        or (load_config().get("atlassian") or {}).get("email")
    )
    if not email:
        pytest.skip("No email configured")
    result = jira_mod.lookup_jira_user(email, max_results=3)
    _assert_ok(result)


def test_get_boards(known_project_key):
    """Boards may be empty for some projects — just check no error."""
    result = jira_mod.get_boards(project_key=known_project_key, max_results=5)
    _assert_ok(result)


def test_get_sprints_for_first_board(known_project_key):
    """Skip if no boards exist for the test project."""
    boards = jira_mod.get_boards(project_key=known_project_key, max_results=1)
    if boards.get("error") or not boards.get("boards"):
        pytest.skip("No boards available for sprint test")
    board_id = boards["boards"][0]["id"]
    result = jira_mod.get_sprints(board_id=board_id, max_results=3)
    _assert_ok(result)
