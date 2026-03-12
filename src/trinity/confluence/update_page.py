#!/usr/bin/env python3
"""Update an existing Confluence page."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_confluence_auth_headers, CONFLUENCE_BASE_URL, format_error
from .get_page import get_confluence_page


def update_confluence_page(
    page_id: str,
    title: Optional[str] = None,
    body: Optional[str] = None,
    body_format: str = "storage",
    version_comment: Optional[str] = None,
    minor_edit: bool = False,
) -> dict:
    """
    Update an existing Confluence page.

    Fetches current version automatically and increments it.

    Args:
        page_id: Page ID to update
        title: New title (keeps existing if not provided)
        body: New body content (keeps existing if not provided)
        body_format: "storage" (HTML) or "wiki"
        version_comment: Comment for this version
        minor_edit: Mark as minor edit

    Returns:
        dict: {"id", "title", "version", "url"}
    """
    # Fetch current page to get version number and existing content
    current = get_confluence_page(page_id, include_body=(body is None))
    if current.get("error"):
        return current

    current_version = current.get("version", 1)
    current_title = current.get("title", "")
    current_body = current.get("body", "") or ""

    payload: dict = {
        "type": "page",
        "title": title or current_title,
        "version": {
            "number": current_version + 1,
            "minorEdit": minor_edit,
        },
        "body": {
            body_format: {
                "value": body if body is not None else current_body,
                "representation": body_format,
            }
        },
    }

    if version_comment:
        payload["version"]["message"] = version_comment

    try:
        response = requests.put(
            f"{CONFLUENCE_BASE_URL}/wiki/rest/api/content/{page_id}",
            headers=get_confluence_auth_headers(),
            json=payload,
            timeout=30,
        )

        if response.status_code != 200:
            return format_error(response.status_code, response.text)

        data = response.json()
        links = data.get("_links", {})
        base_url = links.get("base", "")
        web_ui = links.get("webui", "")

        return {
            "success": True,
            "id": data.get("id"),
            "title": data.get("title"),
            "version": data.get("version", {}).get("number"),
            "url": f"{base_url}{web_ui}" if web_ui else None,
        }

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("update")
@click.argument("page_id")
@click.option("--title", help="New page title")
@click.option("--body", help="New page body (HTML storage format)")
@click.option("--body-file", type=click.Path(exists=True), help="Read body from file")
@click.option("--comment", help="Version comment")
@click.option("--minor", is_flag=True, help="Mark as minor edit")
@click.pass_context
def update_cmd(ctx, page_id, title, body, body_file, comment, minor):
    """Update a Confluence page."""
    if body_file:
        with open(body_file) as f:
            body = f.read()

    if not title and not body:
        raise click.UsageError("Provide at least --title or --body / --body-file")

    result = update_confluence_page(page_id, title=title, body=body, version_comment=comment, minor_edit=minor)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
