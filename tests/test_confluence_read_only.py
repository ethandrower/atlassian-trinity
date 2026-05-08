"""Live read-only Confluence API smoke tests."""

import pytest

from trinity import confluence as conf_mod

pytestmark = pytest.mark.jira_auth


def _assert_ok(result: dict, *expected_fields: str) -> None:
    assert isinstance(result, dict)
    assert not result.get("error"), f"API error: {result}"
    for field in expected_fields:
        assert field in result, f"missing field {field!r}: {list(result.keys())}"


def test_get_spaces():
    result = conf_mod.get_confluence_spaces(max_results=5)
    _assert_ok(result)
    assert "spaces" in result or "values" in result or "count" in result


def test_search_text():
    result = conf_mod.search_confluence("test", max_results=3)
    _assert_ok(result)


def test_list_space_pages_for_first_space():
    spaces = conf_mod.get_confluence_spaces(max_results=1)
    if spaces.get("error"):
        pytest.skip(f"Cannot list spaces: {spaces}")
    candidates = spaces.get("spaces") or spaces.get("values") or []
    if not candidates:
        pytest.skip("No accessible Confluence spaces")
    key = candidates[0].get("key") or candidates[0].get("id")
    if not key:
        pytest.skip(f"No space key in: {candidates[0]}")
    result = conf_mod.list_space_pages(space_key=key, max_results=3)
    _assert_ok(result)
