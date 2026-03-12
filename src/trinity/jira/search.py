#!/usr/bin/env python3
"""Search Jira issues using JQL."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_jira_auth_headers, JIRA_BASE_URL, format_error


def search_jira(
    jql: str,
    max_results: int = 50,
    fields: Optional[list] = None,
    expand: Optional[list] = None,
) -> dict:
    """
    Search Jira issues using JQL.

    Returns:
        {"total": int, "count": int, "issues": [...]}
    """
    if fields is None:
        fields = [
            "summary", "status", "assignee", "priority",
            "created", "updated", "issuetype", "labels",
            "reporter", "description",
        ]

    payload: dict = {"jql": jql, "maxResults": min(max_results, 100), "fields": fields}
    if expand:
        payload["expand"] = expand

    try:
        response = requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/search/jql",
            headers=get_jira_auth_headers(),
            json=payload,
            timeout=30,
        )

        if response.status_code != 200:
            return format_error(response.status_code, response.text)

        data = response.json()
        issues = []
        for issue in data.get("issues", []):
            f = issue.get("fields", {})
            issues.append({
                "key": issue.get("key"),
                "id": issue.get("id"),
                "summary": f.get("summary"),
                "status": f.get("status", {}).get("name") if f.get("status") else None,
                "assignee": f.get("assignee", {}).get("displayName") if f.get("assignee") else "Unassigned",
                "assignee_id": f.get("assignee", {}).get("accountId") if f.get("assignee") else None,
                "reporter": f.get("reporter", {}).get("displayName") if f.get("reporter") else None,
                "priority": f.get("priority", {}).get("name") if f.get("priority") else None,
                "type": f.get("issuetype", {}).get("name") if f.get("issuetype") else None,
                "labels": f.get("labels", []),
                "created": f.get("created"),
                "updated": f.get("updated"),
            })

        return {"total": data.get("total", 0), "count": len(issues), "issues": issues}

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("search")
@click.argument("jql")
@click.option("--max-results", default=50, type=int)
@click.option("--fields", help="Comma-separated field list")
@click.pass_context
def search_cmd(ctx, jql, max_results, fields):
    """Search Jira issues using JQL."""
    field_list = fields.split(",") if fields else None
    result = search_jira(jql, max_results, field_list)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
