"""Resolving "SOURCE <relation> TARGET" into Jira's issueLink payload.

Pure unit tests — no network, no credentials.
"""

from trinity.jira.link_issues import resolve_link

TYPES = [
    {"name": "Blocks", "outward": "blocks", "inward": "is blocked by"},
    {"name": "Duplicate", "outward": "duplicates", "inward": "is duplicated by"},
    {"name": "Relates", "outward": "relates to", "inward": "relates to"},
]


def _keys(payload):
    return payload["type"]["name"], payload["inwardIssue"]["key"], payload["outwardIssue"]["key"]


def test_outward_phrase_keeps_order():
    # Jira reads "inwardIssue duplicates outwardIssue".
    assert _keys(resolve_link("ECD-2", "duplicates", "ECD-1", TYPES)) == ("Duplicate", "ECD-2", "ECD-1")


def test_inward_phrase_swaps_order():
    # "A is blocked by B" is "B blocks A".
    assert _keys(resolve_link("ECD-5", "is blocked by", "ECD-9", TYPES)) == ("Blocks", "ECD-9", "ECD-5")


def test_type_name_reads_outward():
    assert _keys(resolve_link("ECD-2", "Duplicate", "ECD-1", TYPES)) == ("Duplicate", "ECD-2", "ECD-1")


def test_relation_is_case_and_space_insensitive():
    assert _keys(resolve_link("ECD-5", "  Is   Blocked BY ", "ECD-9", TYPES)) == ("Blocks", "ECD-9", "ECD-5")


def test_symmetric_type():
    assert _keys(resolve_link("ECD-1", "relates to", "ECD-2", TYPES)) == ("Relates", "ECD-1", "ECD-2")


def test_unknown_relation():
    assert resolve_link("ECD-1", "fixes", "ECD-2", TYPES) is None
