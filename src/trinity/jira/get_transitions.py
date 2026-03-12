#!/usr/bin/env python3
"""Get available status transitions for a Jira issue."""

import json
import sys

import click
import requests

from ..base import get_jira_auth_headers, JIRA_BASE_URL, format_error


def get_jira_transitions(issue_key: str) -> dict:
    """
    Get available status transitions for a Jira issue.

    Returns:
        {"issue_key", "current_status", "transitions": [{"id", "name", "to_status", "to_category"}]}
    """
    try:
        issue_resp = requests.get(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}",
            headers=get_jira_auth_headers(),
            params={"fields": "status"},
            timeout=30,
        )
        current_status = None
        if issue_resp.status_code == 200:
            current_status = issue_resp.json().get("fields", {}).get("status", {}).get("name")

        response = requests.get(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions",
            headers=get_jira_auth_headers(),
            timeout=30,
        )

        if response.status_code != 200:
            return format_error(response.status_code, response.text)

        data = response.json()
        transitions = [
            {
                "id": t.get("id"),
                "name": t.get("name"),
                "to_status": t.get("to", {}).get("name"),
                "to_category": t.get("to", {}).get("statusCategory", {}).get("name"),
            }
            for t in data.get("transitions", [])
        ]

        return {
            "issue_key": issue_key,
            "current_status": current_status,
            "transitions": transitions,
        }

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("transitions")
@click.argument("issue_key")
@click.pass_context
def transitions_cmd(ctx, issue_key):
    """List available status transitions for a Jira issue."""
    result = get_jira_transitions(issue_key)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
