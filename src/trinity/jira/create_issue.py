#!/usr/bin/env python3
"""Create a Jira issue (Task, Story, Epic, Bug, Sub-task)."""

from __future__ import annotations

from typing import Optional

import requests

from ..base import get_jira_auth_headers, JIRA_BASE_URL, build_adf_comment, format_error


def create_jira_issue(
    project_key: str,
    summary: str,
    issue_type: str = "Task",
    description: Optional[str] = None,
    assignee_id: Optional[str] = None,
    priority: Optional[str] = None,
    labels: Optional[list[str]] = None,
    parent_key: Optional[str] = None,
    epic_key: Optional[str] = None,
    story_points: Optional[float] = None,
    sprint_id: Optional[int] = None,
    fix_version: Optional[str] = None,
    components: Optional[list[str]] = None,
) -> dict:
    """
    Create a Jira issue.

    Args:
        project_key:  Jira project key (e.g. "ECD")
        summary:      Issue title
        issue_type:   "Task", "Story", "Epic", "Bug", "Sub-task"
        description:  Plain text description (converted to ADF)
        assignee_id:  Atlassian account ID
        priority:     "Highest", "High", "Medium", "Low", "Lowest"
        labels:       List of label strings
        parent_key:   Parent issue key. For Stories/Tasks under an Epic in
                      next-gen projects use this. For Sub-tasks use the parent
                      issue key.
        epic_key:     Epic link for classic projects (customfield_10014).
                      Prefer parent_key for next-gen projects.
        story_points: Story point estimate (customfield_10016)
        sprint_id:    Sprint ID to add the issue to (customfield_10020)
        fix_version:  Fix version name
        components:   List of component names
    """
    fields: dict = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type},
    }

    if description:
        fields["description"] = build_adf_body(description)

    if assignee_id:
        fields["assignee"] = {"accountId": assignee_id}

    if priority:
        fields["priority"] = {"name": priority}

    if labels:
        fields["labels"] = labels

    if components:
        fields["components"] = [{"name": c} for c in components]

    if fix_version:
        fields["fixVersions"] = [{"name": fix_version}]

    # Parent / Epic linking — try next-gen style first (parent field),
    # fall back to classic epic link custom field if epic_key is provided separately.
    if parent_key:
        fields["parent"] = {"key": parent_key}
    elif epic_key:
        # Classic projects: customfield_10014 is the Epic Link field
        fields["customfield_10014"] = epic_key

    if story_points is not None:
        fields["customfield_10016"] = story_points

    if sprint_id is not None:
        fields["customfield_10020"] = {"id": sprint_id}

    try:
        response = requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue",
            headers=get_jira_auth_headers(),
            json={"fields": fields},
            timeout=30,
        )

        if response.status_code not in (200, 201):
            try:
                err_body = response.json()
                # Jira returns errors as {"errorMessages": [...], "errors": {...}}
                msgs = err_body.get("errorMessages", [])
                field_errs = err_body.get("errors", {})
                if field_errs:
                    msgs += [f"{k}: {v}" for k, v in field_errs.items()]
                message = "; ".join(msgs) if msgs else response.text
            except Exception:
                message = response.text
            return format_error(response.status_code, message)

        data = response.json()
        issue_key = data.get("key", "")
        issue_id = data.get("id", "")

        result: dict = {
            "success": True,
            "key": issue_key,
            "id": issue_id,
            "issue_type": issue_type,
            "summary": summary,
            "project": project_key,
        }

        from ..base.client import JIRA_WEB_URL
        if JIRA_WEB_URL and issue_key:
            result["url"] = f"{JIRA_WEB_URL.rstrip('/')}/browse/{issue_key}"

        return result

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


def build_adf_body(text: str) -> dict:
    """Wrap plain text in a minimal ADF document body."""
    paragraphs = []
    for line in text.split("\n"):
        if line.strip():
            paragraphs.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": line}],
            })
    if not paragraphs:
        paragraphs = [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]
    return {"version": 1, "type": "doc", "content": paragraphs}
