#!/usr/bin/env python3
"""Get issues in a Jira sprint."""

import json
import sys
from typing import List, Optional

import click
import requests

from ..base import get_jira_auth_headers, AGILE_BASE_URL, format_error


def get_sprint_issues(
    sprint_id: int,
    status: Optional[str] = None,
    issue_types: Optional[List[str]] = None,
    max_results: int = 100,
) -> dict:
    """Get all issues in a sprint with optional status/type filters."""
    params: dict = {
        "maxResults": min(max_results, 100),
        "fields": "summary,status,issuetype,assignee,priority,customfield_10016,resolution,labels,description",
    }

    jql_parts = []
    if status:
        jql_parts.append(f'status = "{status}"')
    if issue_types:
        types_str = ", ".join(f'"{t}"' for t in issue_types)
        jql_parts.append(f"issuetype in ({types_str})")
    if jql_parts:
        params["jql"] = " AND ".join(jql_parts)

    try:
        response = requests.get(
            f"{AGILE_BASE_URL}/sprint/{sprint_id}/issue",
            headers=get_jira_auth_headers(),
            params=params,
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
                "description": f.get("description"),
                "status": f.get("status", {}).get("name") if f.get("status") else None,
                "type": f.get("issuetype", {}).get("name") if f.get("issuetype") else None,
                "assignee": f.get("assignee", {}).get("displayName") if f.get("assignee") else "Unassigned",
                "priority": f.get("priority", {}).get("name") if f.get("priority") else None,
                "story_points": f.get("customfield_10016"),
                "resolution": f.get("resolution", {}).get("name") if f.get("resolution") else None,
                "labels": f.get("labels", []),
            })

        return {
            "sprint_id": sprint_id,
            "total": data.get("total", len(issues)),
            "count": len(issues),
            "issues": issues,
        }

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


def get_completed_sprint_issues(sprint_id: int, exclude_types: Optional[List[str]] = None) -> dict:
    """Get only completed issues from a sprint, grouped by type."""
    result = get_sprint_issues(sprint_id, status="Done", max_results=100)
    if result.get("error"):
        return result

    if exclude_types:
        result["issues"] = [i for i in result["issues"] if i["type"] not in exclude_types]
        result["count"] = len(result["issues"])

    by_type: dict = {}
    for issue in result["issues"]:
        t = issue["type"] or "Other"
        by_type.setdefault(t, []).append(issue)
    result["by_type"] = by_type

    return result


@click.command("sprint-issues")
@click.argument("sprint_id", type=int)
@click.option("--status", help="Filter by status")
@click.option("--types", multiple=True, help="Filter by issue types")
@click.option("--completed-only", is_flag=True, help="Only show Done issues")
@click.option("--max-results", default=100, type=int)
@click.pass_context
def sprint_issues_cmd(ctx, sprint_id, status, types, completed_only, max_results):
    """Get issues in a Jira sprint."""
    if completed_only:
        result = get_completed_sprint_issues(sprint_id)
    else:
        result = get_sprint_issues(sprint_id, status, list(types) or None, max_results)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
