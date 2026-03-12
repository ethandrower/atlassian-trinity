#!/usr/bin/env python3
"""Get a Confluence page by ID."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_confluence_auth_headers, CONFLUENCE_BASE_URL, format_error


def get_confluence_page(
    page_id: str,
    include_body: bool = True,
    include_ancestors: bool = False,
    version: Optional[int] = None,
) -> dict:
    """
    Get a Confluence page by ID.

    Args:
        page_id: The page ID (numeric string)
        include_body: Include rendered body content (default True)
        include_ancestors: Include parent page chain
        version: Fetch a specific version (default: latest)

    Returns:
        dict: {
            "id", "title", "space_key", "space_name",
            "status", "body", "url", "version",
            "created", "updated", "author", "ancestors"
        }
    """
    params: dict = {"expand": "space,version,ancestors,body.storage"}
    if not include_body:
        params["expand"] = "space,version,ancestors"
    if version is not None:
        params["version"] = version

    try:
        response = requests.get(
            f"{CONFLUENCE_BASE_URL}/wiki/rest/api/content/{page_id}",
            headers=get_confluence_auth_headers(),
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            return format_error(response.status_code, response.text)

        data = response.json()

        body_text = None
        if include_body:
            body_storage = data.get("body", {}).get("storage", {})
            body_text = body_storage.get("value")

        ancestors = []
        if include_ancestors:
            ancestors = [
                {"id": a.get("id"), "title": a.get("title")}
                for a in data.get("ancestors", [])
            ]

        version_data = data.get("version", {})
        space_data = data.get("space", {})

        # Build web URL
        links = data.get("_links", {})
        base_url = links.get("base", "")
        web_ui = links.get("webui", "")
        url = f"{base_url}{web_ui}" if base_url and web_ui else None

        return {
            "id": data.get("id"),
            "title": data.get("title"),
            "status": data.get("status"),
            "space_key": space_data.get("key"),
            "space_name": space_data.get("name"),
            "version": version_data.get("number"),
            "body": body_text,
            "url": url,
            "created": version_data.get("when") if version_data.get("number") == 1 else None,
            "updated": version_data.get("when"),
            "author": version_data.get("by", {}).get("displayName"),
            "ancestors": ancestors,
        }

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("get")
@click.argument("page_id")
@click.option("--no-body", is_flag=True, help="Exclude body content")
@click.option("--ancestors", is_flag=True, help="Include ancestor pages")
@click.pass_context
def get_cmd(ctx, page_id, no_body, ancestors):
    """Get a Confluence page by ID."""
    result = get_confluence_page(page_id, include_body=not no_body, include_ancestors=ancestors)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
