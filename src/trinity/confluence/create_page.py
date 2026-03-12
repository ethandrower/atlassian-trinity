#!/usr/bin/env python3
"""Create a new Confluence page."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_confluence_auth_headers, CONFLUENCE_BASE_URL, format_error


def create_confluence_page(
    space_key: str,
    title: str,
    body: str,
    parent_id: Optional[str] = None,
    body_format: str = "storage",
) -> dict:
    """
    Create a new Confluence page.

    Args:
        space_key: The space to create the page in (e.g., "ENG")
        title: Page title
        body: Page content (HTML storage format by default, or wiki markup)
        parent_id: Optional parent page ID
        body_format: "storage" (HTML) or "wiki" (wiki markup)

    Returns:
        dict: {"id", "title", "url", "version", "space_key"}
    """
    payload: dict = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {
            body_format: {
                "value": body,
                "representation": body_format,
            }
        },
    }

    if parent_id:
        payload["ancestors"] = [{"id": parent_id}]

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
        links = data.get("_links", {})
        base_url = links.get("base", "")
        web_ui = links.get("webui", "")

        return {
            "success": True,
            "id": data.get("id"),
            "title": data.get("title"),
            "space_key": data.get("space", {}).get("key"),
            "version": data.get("version", {}).get("number"),
            "url": f"{base_url}{web_ui}" if web_ui else None,
        }

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("create")
@click.option("--space", required=True, help="Space key (e.g., ENG)")
@click.option("--title", required=True, help="Page title")
@click.option("--body", help="Page body content (HTML storage format)")
@click.option("--body-file", type=click.Path(exists=True), help="Read body from file")
@click.option("--parent", help="Parent page ID")
@click.option("--format", "body_format", default="storage", type=click.Choice(["storage", "wiki"]))
@click.pass_context
def create_cmd(ctx, space, title, body, body_file, parent, body_format):
    """Create a new Confluence page."""
    if body_file:
        with open(body_file) as f:
            body = f.read()
    if not body:
        raise click.UsageError("Provide --body or --body-file")

    result = create_confluence_page(space, title, body, parent, body_format)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
