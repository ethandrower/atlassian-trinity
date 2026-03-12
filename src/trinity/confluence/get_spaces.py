#!/usr/bin/env python3
"""List Confluence spaces."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_confluence_auth_headers, CONFLUENCE_BASE_URL, format_error


def get_confluence_spaces(
    search: Optional[str] = None,
    space_type: Optional[str] = None,
    max_results: int = 50,
) -> dict:
    """
    List Confluence spaces.

    Args:
        search: Filter by space name or key
        space_type: "global" or "personal"
        max_results: Maximum results

    Returns:
        dict: {"count", "spaces": [{"key", "name", "type", "url"}]}
    """
    params: dict = {
        "limit": min(max_results, 100),
        "expand": "description.plain",
    }
    if space_type:
        params["type"] = space_type

    try:
        response = requests.get(
            f"{CONFLUENCE_BASE_URL}/wiki/rest/api/space",
            headers=get_confluence_auth_headers(),
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            return format_error(response.status_code, response.text)

        data = response.json()
        base_url = data.get("_links", {}).get("base", "")

        spaces = []
        for s in data.get("results", []):
            name = s.get("name", "")
            key = s.get("key", "")

            # Apply search filter client-side
            if search and search.lower() not in name.lower() and search.lower() not in key.lower():
                continue

            links = s.get("_links", {})
            spaces.append({
                "key": key,
                "name": name,
                "type": s.get("type"),
                "description": s.get("description", {}).get("plain", {}).get("value"),
                "url": f"{base_url}{links.get('webui', '')}" if links.get("webui") else None,
            })

        return {"count": len(spaces), "total": data.get("size", len(spaces)), "spaces": spaces}

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("spaces")
@click.option("--search", help="Filter by name or key")
@click.option("--type", "space_type", type=click.Choice(["global", "personal"]))
@click.option("--max-results", default=50, type=int)
@click.pass_context
def spaces_cmd(ctx, search, space_type, max_results):
    """List Confluence spaces."""
    result = get_confluence_spaces(search, space_type, max_results)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
