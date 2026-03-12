#!/usr/bin/env python3
"""Find Jira users by name or email."""

import json
import sys

import click
import requests

from ..base import get_jira_auth_headers, JIRA_BASE_URL, format_error


def lookup_jira_user(query: str, max_results: int = 10) -> dict:
    """Search Jira users by name or email. Returns account IDs for mentions/assignment."""
    try:
        response = requests.get(
            f"{JIRA_BASE_URL}/rest/api/3/user/search",
            headers=get_jira_auth_headers(),
            params={"query": query, "maxResults": max_results},
            timeout=30,
        )

        if response.status_code != 200:
            return format_error(response.status_code, response.text)

        users = [
            {
                "account_id": u.get("accountId"),
                "display_name": u.get("displayName"),
                "email": u.get("emailAddress"),
                "active": u.get("active", True),
                "account_type": u.get("accountType"),
            }
            for u in response.json()
        ]

        return {"query": query, "count": len(users), "users": users}

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("user")
@click.argument("query")
@click.option("--max-results", default=10, type=int)
@click.pass_context
def user_cmd(ctx, query, max_results):
    """Look up a Jira user by name or email."""
    result = lookup_jira_user(query, max_results)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
