#!/usr/bin/env python3
"""Create links between Jira issues ("ECD-1 duplicates ECD-2", "ECD-3 blocks ECD-4")."""

from typing import Optional

import requests

from ..base import get_jira_auth_headers, JIRA_BASE_URL, build_adf_comment, format_error


def get_link_types() -> dict:
    """List the link types this Jira site defines, with both reading directions."""
    try:
        response = requests.get(
            f"{JIRA_BASE_URL}/rest/api/3/issueLinkType",
            headers=get_jira_auth_headers(),
            timeout=30,
        )
        if response.status_code != 200:
            return format_error(response.status_code, response.text)
        types = [
            {"name": t.get("name"), "outward": t.get("outward"), "inward": t.get("inward")}
            for t in response.json().get("issueLinkTypes", [])
        ]
        return {"success": True, "link_types": types}
    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


def resolve_link(source: str, relation: str, target: str, link_types: list) -> Optional[dict]:
    """
    Turn "SOURCE <relation> TARGET" into Jira's link payload.

    `relation` may be a type's outward phrase ("duplicates", "blocks"), its
    inward phrase ("is duplicated by", "is blocked by"), or the type name
    ("Duplicate"), which reads in the outward direction.

    Jira's payload reads "inwardIssue <outward phrase> outwardIssue", so an
    outward phrase keeps the order and an inward phrase swaps it.
    Returns None when nothing matches.
    """
    wanted = " ".join(relation.lower().split())
    for t in link_types:
        outward = (t.get("outward") or "").lower()
        inward = (t.get("inward") or "").lower()
        name = (t.get("name") or "").lower()
        if wanted in (outward, name):
            return {"type": {"name": t["name"]},
                    "inwardIssue": {"key": source}, "outwardIssue": {"key": target}}
        if wanted == inward:
            return {"type": {"name": t["name"]},
                    "inwardIssue": {"key": target}, "outwardIssue": {"key": source}}
    return None


def link_jira_issues(source: str, relation: str, target: str,
                     comment: Optional[str] = None) -> dict:
    """Link two issues so that "SOURCE <relation> TARGET" reads true in Jira."""
    types = get_link_types()
    if types.get("error"):
        return types

    payload = resolve_link(source, relation, target, types["link_types"])
    if payload is None:
        phrases = sorted({p for t in types["link_types"]
                          for p in (t["outward"], t["inward"]) if p})
        return format_error(400, f"Unknown link relation '{relation}'. "
                                 f"Use one of: {', '.join(phrases)}")
    if comment:
        payload["comment"] = {"body": build_adf_comment(comment)}

    try:
        response = requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/issueLink",
            headers=get_jira_auth_headers(),
            json=payload,
            timeout=30,
        )
        if response.status_code not in (200, 201):
            return format_error(response.status_code, response.text)
        return {
            "success": True,
            "link": f"{source} {relation} {target}",
            "type": payload["type"]["name"],
            "inward_issue": payload["inwardIssue"]["key"],
            "outward_issue": payload["outwardIssue"]["key"],
        }
    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))
