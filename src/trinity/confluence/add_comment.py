#!/usr/bin/env python3
"""Add a comment to a Confluence page."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_confluence_auth_headers, CONFLUENCE_BASE_URL, format_error


def add_confluence_comment(
    page_id: str,
    body: str,
    body_format: str = "storage",
    parent_comment_id: Optional[str] = None,
) -> dict:
    """
    Add a footer comment to a Confluence page.

    Args:
        page_id: Page to comment on
        body: Comment text (HTML storage format or plain text wrapped in <p> tags)
        body_format: "storage" (HTML) or "wiki"
        parent_comment_id: Reply to an existing comment

    Returns:
        dict: {"success", "comment_id", "page_id", "author", "created"}
    """
    # Wrap plain text in paragraph tags for storage format
    if body_format == "storage" and not body.strip().startswith("<"):
        body = f"<p>{body}</p>"

    payload: dict = {
        "type": "comment",
        "container": {"id": page_id, "type": "page"},
        "body": {
            body_format: {
                "value": body,
                "representation": body_format,
            }
        },
    }

    if parent_comment_id:
        payload["ancestors"] = [{"type": "comment", "id": parent_comment_id}]

    try:
        response = requests.post(
            f"{CONFLUENCE_BASE_URL}/wiki/rest/api/content",
            headers=get_confluence_auth_headers(),
            json=payload,
            timeout=30,
        )

        if response.status_code not in (200, 201):
            return format_error(response.status_code, response.text)

        data = response.json()
        return {
            "success": True,
            "comment_id": data.get("id"),
            "page_id": page_id,
            "author": data.get("version", {}).get("by", {}).get("displayName"),
            "created": data.get("version", {}).get("when"),
        }

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("comment")
@click.argument("page_id")
@click.argument("text")
@click.option("--reply-to", help="Parent comment ID to reply to")
@click.pass_context
def comment_cmd(ctx, page_id, text, reply_to):
    """Add a comment to a Confluence page."""
    result = add_confluence_comment(page_id, text, parent_comment_id=reply_to)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
