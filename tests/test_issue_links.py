"""Normalising Jira issuelinks.

Pure unit tests over the raw shapes Jira returns — no network, no credentials.
"""

from trinity.jira.issue_links import normalize_links


def _link(inward=None, outward=None, key="ECD-1", status="To Do", category="new"):
    partner = {
        "key": key,
        "fields": {
            "summary": f"summary {key}",
            "status": {"name": status, "statusCategory": {"key": category}},
        },
    }
    link = {"type": {"name": "Blocks", "inward": inward, "outward": outward}}
    if inward:
        link["inwardIssue"] = partner
    else:
        link["outwardIssue"] = partner
    return link


def test_no_links_is_not_blocked():
    assert normalize_links({}) == {
        "links": [],
        "blocked_by": [],
        "blocks": [],
        "is_blocked": False,
    }


def test_open_blocker_blocks():
    out = normalize_links({"issuelinks": [_link(inward="is blocked by", key="ECD-9")]})
    assert out["blocked_by"] == ["ECD-9"]
    assert out["is_blocked"] is True


def test_resolved_blocker_does_not_block():
    """A dependency that already shipped is history, not a blocker."""
    out = normalize_links(
        {
            "issuelinks": [
                _link(inward="is blocked by", key="ECD-9", status="Done", category="done")
            ]
        }
    )
    assert out["blocked_by"] == ["ECD-9"], "still reported, so nothing is hidden"
    assert out["is_blocked"] is False, "but it must not stall work"


def test_any_open_blocker_blocks():
    out = normalize_links(
        {
            "issuelinks": [
                _link(inward="is blocked by", key="ECD-1", status="Done", category="done"),
                _link(inward="is blocked by", key="ECD-2", status="To Do", category="new"),
            ]
        }
    )
    assert out["is_blocked"] is True
    assert sorted(out["blocked_by"]) == ["ECD-1", "ECD-2"]


def test_resolution_uses_category_not_status_name():
    """Status names are project-configurable; the category is not."""
    out = normalize_links(
        {
            "issuelinks": [
                _link(inward="is blocked by", key="ECD-4", status="Shipped", category="done")
            ]
        }
    )
    assert out["is_blocked"] is False


def test_blocking_something_else_does_not_block_you():
    out = normalize_links({"issuelinks": [_link(outward="blocks", key="ECD-5")]})
    assert out["blocks"] == ["ECD-5"]
    assert out["blocked_by"] == []
    assert out["is_blocked"] is False


def test_relates_to_is_neither():
    out = normalize_links({"issuelinks": [_link(outward="relates to", key="ECD-7")]})
    assert out["blocks"] == []
    assert out["blocked_by"] == []
    assert out["is_blocked"] is False
    assert out["links"][0]["relationship"] == "relates to"


def test_link_stub_without_a_partner_is_skipped():
    """Jira can return a link with neither side populated."""
    assert normalize_links({"issuelinks": [{"type": {"name": "Blocks"}}]})["links"] == []


def test_summary_and_status_are_carried():
    out = normalize_links({"issuelinks": [_link(inward="is blocked by", key="ECD-3")]})
    link = out["links"][0]
    assert link["key"] == "ECD-3"
    assert link["summary"] == "summary ECD-3"
    assert link["status"] == "To Do"
    assert link["resolved"] is False
