#!/usr/bin/env python3
"""Get full details of a Jira issue."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_jira_auth_headers, JIRA_BASE_URL, format_error


def get_jira_issue(
    issue_key: str,
    fields: Optional[list] = None,
    expand: Optional[list] = None,
    include_comments: bool = False,
) -> dict:
    """
    Get full details of a Jira issue.

    Returns simplified structure with all common fields.
    """
    params = {}
    if fields:
        params["fields"] = ",".join(fields)

    expand_list = list(expand or [])
    if include_comments and "renderedFields" not in expand_list:
        expand_list.append("renderedFields")
    if expand_list:
        params["expand"] = ",".join(expand_list)

    try:
        response = requests.get(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}",
            headers=get_jira_auth_headers(),
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            return format_error(response.status_code, response.text)

        data = response.json()
        f = data.get("fields", {})

        result = {
            "key": data.get("key"),
            "id": data.get("id"),
            "self": data.get("self"),
            "summary": f.get("summary"),
            "description": _extract_text_from_adf(f.get("description")),
            "status": f.get("status", {}).get("name") if f.get("status") else None,
            "status_category": f.get("status", {}).get("statusCategory", {}).get("name") if f.get("status") else None,
            "assignee": {
                "name": f.get("assignee", {}).get("displayName") if f.get("assignee") else "Unassigned",
                "account_id": f.get("assignee", {}).get("accountId") if f.get("assignee") else None,
                "email": f.get("assignee", {}).get("emailAddress") if f.get("assignee") else None,
            },
            "reporter": {
                "name": f.get("reporter", {}).get("displayName") if f.get("reporter") else None,
                "account_id": f.get("reporter", {}).get("accountId") if f.get("reporter") else None,
            },
            "priority": f.get("priority", {}).get("name") if f.get("priority") else None,
            "type": f.get("issuetype", {}).get("name") if f.get("issuetype") else None,
            "labels": f.get("labels", []),
            "created": f.get("created"),
            "updated": f.get("updated"),
            "resolution": f.get("resolution", {}).get("name") if f.get("resolution") else None,
            "sprint": _extract_sprint_info(f),
            "epic_key": f.get("parent", {}).get("key") if f.get("parent") else None,
            "story_points": f.get("customfield_10016"),
        }

        if include_comments:
            result["comments"] = _get_issue_comments(issue_key)

        return result

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


def _extract_text_from_adf(adf: Optional[dict]) -> Optional[str]:
    if not adf:
        return None
    parts = []

    def _recurse(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                parts.append(node.get("text", ""))
            for child in node.get("content", []):
                _recurse(child)
        elif isinstance(node, list):
            for item in node:
                _recurse(item)

    _recurse(adf)
    return " ".join(parts) if parts else None


def _extract_sprint_info(fields_data: dict) -> Optional[dict]:
    sprint_field = fields_data.get("customfield_10020")
    if sprint_field and isinstance(sprint_field, list) and sprint_field:
        sprint = sprint_field[0]
        if isinstance(sprint, dict):
            return {
                "id": sprint.get("id"),
                "name": sprint.get("name"),
                "state": sprint.get("state"),
            }
    return None


def _get_issue_comments(issue_key: str, max_results: int = 20) -> list:
    try:
        response = requests.get(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/comment",
            headers=get_jira_auth_headers(),
            params={"maxResults": max_results, "orderBy": "-created"},
            timeout=30,
        )
        if response.status_code != 200:
            return []
        data = response.json()
        return [
            {
                "id": c.get("id"),
                "author": c.get("author", {}).get("displayName"),
                "author_id": c.get("author", {}).get("accountId"),
                "body": _extract_text_from_adf(c.get("body")),
                "created": c.get("created"),
                "updated": c.get("updated"),
            }
            for c in data.get("comments", [])
        ]
    except Exception:
        return []


@click.command("show")
@click.argument("issue_key")
@click.option("--fields", help="Comma-separated field list")
@click.option("--comments", "include_comments", is_flag=True, help="Include comments")
@click.pass_context
def show_cmd(ctx, issue_key, fields, include_comments):
    """Show full details of a Jira issue."""
    field_list = fields.split(",") if fields else None
    result = get_jira_issue(issue_key, fields=field_list, include_comments=include_comments)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
