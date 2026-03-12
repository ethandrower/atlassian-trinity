#!/usr/bin/env python3
"""Update fields on a Jira issue."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_jira_auth_headers, JIRA_BASE_URL, format_error


def edit_jira_issue(
    issue_key: str,
    fields: Optional[dict] = None,
    update: Optional[dict] = None,
) -> dict:
    """
    Update fields on a Jira issue.

    Args:
        fields: {"summary": "...", "priority": {"name": "High"}, ...}
        update: {"labels": [{"add": "urgent"}]}
    """
    if not fields and not update:
        return format_error(400, "No fields or updates provided")

    payload: dict = {}
    if fields:
        payload["fields"] = fields
    if update:
        payload["update"] = update

    try:
        response = requests.put(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}",
            headers=get_jira_auth_headers(),
            json=payload,
            timeout=30,
        )

        if response.status_code == 204:
            return {
                "success": True,
                "issue_key": issue_key,
                "fields_updated": list(fields.keys()) if fields else [],
                "updates_applied": list(update.keys()) if update else [],
            }

        return format_error(response.status_code, response.text)

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("edit")
@click.argument("issue_key")
@click.option("--assignee", help="Account ID (use 'none' to unassign)")
@click.option("--priority", help="Priority name (High, Medium, Low)")
@click.option("--summary", help="New title")
@click.option("--labels", help="Comma-separated labels (replaces existing)")
@click.option("--add-labels", help="Comma-separated labels to add")
@click.option("--remove-labels", help="Comma-separated labels to remove")
@click.pass_context
def edit_cmd(ctx, issue_key, assignee, priority, summary, labels, add_labels, remove_labels):
    """Update fields on a Jira issue."""
    fields: dict = {}
    update: dict = {}

    if assignee:
        fields["assignee"] = None if assignee.lower() == "none" else {"accountId": assignee}
    if priority:
        fields["priority"] = {"name": priority}
    if summary:
        fields["summary"] = summary
    if labels:
        fields["labels"] = [l.strip() for l in labels.split(",")]
    if add_labels:
        update["labels"] = [{"add": l.strip()} for l in add_labels.split(",")]
    if remove_labels:
        update.setdefault("labels", []).extend(
            [{"remove": l.strip()} for l in remove_labels.split(",")]
        )

    if not fields and not update:
        raise click.UsageError("At least one field update is required")

    result = edit_jira_issue(issue_key, fields or None, update or None)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
