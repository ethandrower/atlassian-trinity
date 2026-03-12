#!/usr/bin/env python3
"""Post a comment to a Jira issue with @mention support."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_jira_auth_headers, JIRA_BASE_URL, build_adf_comment, format_error


def add_jira_comment(
    issue_key: str,
    comment_text: str,
    mentions: Optional[list] = None,
    visibility: Optional[dict] = None,
) -> dict:
    """
    Add a comment to a Jira issue.

    Args:
        mentions: [{"id": "accountId", "name": "Display Name"}, ...]
        visibility: {"type": "role", "value": "Developers"}
    """
    body = build_adf_comment(comment_text, mentions)
    payload: dict = {"body": body}
    if visibility:
        payload["visibility"] = visibility

    try:
        response = requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/comment",
            headers=get_jira_auth_headers(),
            json=payload,
            timeout=30,
        )

        if response.status_code not in (200, 201):
            return format_error(response.status_code, response.text)

        data = response.json()
        return {
            "success": True,
            "comment_id": data.get("id"),
            "issue_key": issue_key,
            "author": data.get("author", {}).get("displayName"),
            "author_id": data.get("author", {}).get("accountId"),
            "created": data.get("created"),
            "self": data.get("self"),
        }

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("comment")
@click.argument("issue_key")
@click.argument("text")
@click.option("--mention", nargs=2, multiple=True, metavar="ACCOUNT_ID NAME")
@click.pass_context
def comment_cmd(ctx, issue_key, text, mention):
    """Add a comment to a Jira issue."""
    mentions = [{"id": m[0], "name": m[1]} for m in mention] if mention else None
    result = add_jira_comment(issue_key, text, mentions)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
