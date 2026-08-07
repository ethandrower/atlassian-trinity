"""Normalise Jira's issuelinks into something a caller can act on.

Jira reports a link from whichever side you fetched it, so the same dependency
appears as "blocks" on one issue and "is blocked by" on the other, and the partner
issue lives under `inwardIssue` or `outwardIssue` depending on direction. Callers
that only want to know *can I start this ticket* should not have to unpick that.

The `resolved` flag matters as much as the link itself: a "blocked by" pointing at a
finished ticket is history, not a blocker. Reporting an issue as blocked because of a
dependency that shipped last month would stall work for no reason.
"""

from __future__ import annotations

from typing import Any

# Jira's statusCategory for finished work. Status *names* are project-configurable
# ("Done", "Closed", "Shipped"), the category is not — so match on the category.
DONE_CATEGORY = "done"


def _partner(link: dict) -> tuple[str, dict]:
    """Return (relationship_phrase, partner_issue) for one raw link."""
    link_type = link.get("type") or {}
    if link.get("inwardIssue"):
        return link_type.get("inward") or "relates to", link["inwardIssue"]
    if link.get("outwardIssue"):
        return link_type.get("outward") or "relates to", link["outwardIssue"]
    return link_type.get("name") or "relates to", {}


def _is_resolved(issue: dict) -> bool:
    status = (issue.get("fields") or {}).get("status") or {}
    category = (status.get("statusCategory") or {}).get("key") or ""
    return category.lower() == DONE_CATEGORY


def normalize_links(fields: dict[str, Any]) -> dict[str, Any]:
    """Turn raw `issuelinks` into links / blocked_by / blocks / is_blocked.

    `blocked_by` and `blocks` list every linked key regardless of state, so nothing is
    hidden. `is_blocked` answers the narrower question the development loop actually
    asks: is there an *unfinished* dependency standing in the way right now.
    """
    links: list[dict[str, Any]] = []
    blocked_by: list[str] = []
    blocks: list[str] = []
    open_blockers = 0

    for raw in fields.get("issuelinks") or []:
        relationship, partner = _partner(raw)
        key = partner.get("key")
        if not key:
            continue
        partner_fields = partner.get("fields") or {}
        resolved = _is_resolved(partner)
        links.append(
            {
                "relationship": relationship,
                "key": key,
                "summary": partner_fields.get("summary"),
                "status": (partner_fields.get("status") or {}).get("name"),
                "resolved": resolved,
            }
        )
        phrase = relationship.lower()
        if "blocked by" in phrase:
            blocked_by.append(key)
            if not resolved:
                open_blockers += 1
        elif phrase.startswith("blocks"):
            blocks.append(key)

    return {
        "links": links,
        "blocked_by": blocked_by,
        "blocks": blocks,
        "is_blocked": open_blockers > 0,
    }
