#!/usr/bin/env python3
"""Get child pages of a Confluence page."""

import json
import sys

import click
import requests

from ..base import get_confluence_auth_headers, CONFLUENCE_BASE_URL, format_error


def get_page_children(page_id: str, max_results: int = 50) -> dict:
    """
    Get child pages of a Confluence page.

    Returns:
        dict: {"page_id", "count", "children": [{"id", "title", "url"}]}
    """
    params = {
        "expand": "version,space",
        "limit": min(max_results, 100),
    }

    try:
        response = requests.get(
            f"{CONFLUENCE_BASE_URL}/wiki/rest/api/content/{page_id}/child/page",
            headers=get_confluence_auth_headers(),
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            return format_error(response.status_code, response.text)

        data = response.json()
        base_url = data.get("_links", {}).get("base", "")

        children = []
        for page in data.get("results", []):
            links = page.get("_links", {})
            children.append({
                "id": page.get("id"),
                "title": page.get("title"),
                "status": page.get("status"),
                "updated": page.get("version", {}).get("when"),
                "author": page.get("version", {}).get("by", {}).get("displayName"),
                "url": f"{base_url}{links.get('webui', '')}" if links.get("webui") else None,
            })

        return {
            "page_id": page_id,
            "count": len(children),
            "total": data.get("size", len(children)),
            "children": children,
        }

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("children")
@click.argument("page_id")
@click.option("--max-results", default=50, type=int)
@click.pass_context
def children_cmd(ctx, page_id, max_results):
    """List child pages of a Confluence page."""
    result = get_page_children(page_id, max_results)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
