#!/usr/bin/env python3
"""Get completed issues for release notes."""

import json
import sys
from typing import List, Optional

import click
import requests

from ..base import get_jira_auth_headers, JIRA_BASE_URL, format_error


def _extract_text_from_adf(adf: dict) -> str:
    texts = []

    def _recurse(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                texts.append(node.get("text", ""))
            for child in node.get("content", []):
                _recurse(child)
        elif isinstance(node, list):
            for item in node:
                _recurse(item)

    _recurse(adf)
    return " ".join(texts)


def get_release_issues(
    fix_version: Optional[str] = None,
    sprint_name: Optional[str] = None,
    days: int = 14,
    project: str = "ECD",
    exclude_types: Optional[List[str]] = None,
    max_results: int = 100,
) -> dict:
    """Get completed Jira issues for release notes, grouped by type."""
    if exclude_types is None:
        exclude_types = ["Sub-task", "Epic"]

    jql_parts = [f"project = {project}", "statusCategory = Done"]

    if fix_version:
        jql_parts.append(f'fixVersion = "{fix_version}"')
    elif sprint_name:
        jql_parts.append(f'sprint = "{sprint_name}"')
    else:
        jql_parts.append(f"status CHANGED TO Complete AFTER -{days}d")

    if exclude_types:
        types_str = ", ".join(f'"{t}"' for t in exclude_types)
        jql_parts.append(f"issuetype NOT IN ({types_str})")

    jql_parts.append("ORDER BY updated DESC")
    jql = " AND ".join(jql_parts[:-1]) + " " + jql_parts[-1]

    try:
        payload = {
            "jql": jql,
            "maxResults": min(max_results, 100),
            "fields": [
                "summary", "description", "status", "issuetype",
                "assignee", "labels", "priority", "updated",
                "fixVersions", "customfield_10016",
            ],
        }

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
        by_type: dict = {}

        for issue in data.get("issues", []):
            f = issue.get("fields", {})
            issue_type = f.get("issuetype", {}).get("name") if f.get("issuetype") else "Other"

            description = ""
            if f.get("description"):
                desc = f["description"]
                description = _extract_text_from_adf(desc) if isinstance(desc, dict) else str(desc)

            entry = {
                "key": issue.get("key"),
                "id": issue.get("id"),
                "summary": f.get("summary"),
                "description": description[:500] if description else "",
                "status": f.get("status", {}).get("name") if f.get("status") else None,
                "type": issue_type,
                "assignee": f.get("assignee", {}).get("displayName") if f.get("assignee") else "Unassigned",
                "priority": f.get("priority", {}).get("name") if f.get("priority") else None,
                "story_points": f.get("customfield_10016"),
                "labels": f.get("labels", []),
                "fix_versions": [v.get("name") for v in f.get("fixVersions", [])],
                "updated": f.get("updated"),
            }

            issues.append(entry)
            by_type.setdefault(issue_type, []).append(entry)

        return {
            "jql": jql,
            "total": data.get("total", len(issues)),
            "count": len(issues),
            "issues": issues,
            "by_type": by_type,
        }

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


def get_current_sprint_completed(project: str = "ECD") -> dict:
    """Get completed issues from the currently active sprint."""
    jql = f"project = {project} AND sprint in openSprints() AND statusCategory = Done ORDER BY updated DESC"
    try:
        payload = {
            "jql": jql,
            "maxResults": 100,
            "fields": [
                "summary", "description", "status", "issuetype",
                "assignee", "labels", "priority", "updated",
                "fixVersions", "customfield_10016",
            ],
        }
        response = requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/search/jql",
            headers=get_jira_auth_headers(),
            json=payload,
            timeout=30,
        )

        if response.status_code != 200 or response.json().get("total", 0) == 0:
            return get_release_issues(days=14, project=project)

        data = response.json()
        issues = []
        by_type: dict = {}

        for issue in data.get("issues", []):
            f = issue.get("fields", {})
            issue_type = f.get("issuetype", {}).get("name") if f.get("issuetype") else "Other"
            if issue_type in ["Sub-task", "Epic"]:
                continue

            description = ""
            if f.get("description"):
                desc = f["description"]
                description = _extract_text_from_adf(desc) if isinstance(desc, dict) else str(desc)

            entry = {
                "key": issue.get("key"),
                "id": issue.get("id"),
                "summary": f.get("summary"),
                "description": description[:500] if description else "",
                "status": f.get("status", {}).get("name") if f.get("status") else None,
                "type": issue_type,
                "assignee": f.get("assignee", {}).get("displayName") if f.get("assignee") else "Unassigned",
                "priority": f.get("priority", {}).get("name") if f.get("priority") else None,
                "story_points": f.get("customfield_10016"),
                "labels": f.get("labels", []),
                "fix_versions": [v.get("name") for v in f.get("fixVersions", [])],
                "updated": f.get("updated"),
            }

            issues.append(entry)
            by_type.setdefault(issue_type, []).append(entry)

        return {
            "jql": jql,
            "total": len(issues),
            "count": len(issues),
            "issues": issues,
            "by_type": by_type,
            "source": "current_sprint",
        }

    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("release-issues")
@click.option("--fix-version", help="Filter by fix version")
@click.option("--sprint", help="Filter by sprint name")
@click.option("--days", default=14, type=int, help="Look back N days")
@click.option("--project", default="ECD", help="Project key")
@click.option("--current-sprint", is_flag=True, help="Use current active sprint")
@click.option("--max-results", default=100, type=int)
@click.pass_context
def release_issues_cmd(ctx, fix_version, sprint, days, project, current_sprint, max_results):
    """Get completed Jira issues for release notes."""
    if current_sprint:
        result = get_current_sprint_completed(project)
    else:
        result = get_release_issues(fix_version, sprint, days, project, max_results=max_results)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
