#!/usr/bin/env python3
"""Search Confluence using CQL (Confluence Query Language)."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_confluence_auth_headers, CONFLUENCE_BASE_URL, format_error


def search_confluence(
    query: str,
    space_key: Optional[str] = None,
    content_type: Optional[str] = None,
    max_results: int = 25,
) -> dict:
    """
    Search Confluence using CQL.

    Args:
        query: Text to search for (wrapped in CQL automatically, or raw CQL)
        space_key: Limit results to a specific space
        content_type: "page", "blogpost", or "comment" (default: page)
        max_results: Maximum results to return

    Returns:
        dict: {"total", "count", "results": [{"id", "title", "space", "url", "excerpt", "updated"}]}
    """
    # Build CQL
    if " AND " in query or " OR " in query or query.startswith("type ="):
        cql = query  # Already CQL
    else:
        cql = f'text ~ "{query}"'

    if space_key:
        cql = f'{cql} AND space = "{space_key}"'

    ctype = content_type or "page"
    cql = f'{cql} AND type = "{ctype}"'
    cql = f"{cql} ORDER BY lastmodified DESC"

    params = {
        "cql": cql,
        "limit": min(max_results, 50),
        "expand": "space,version,ancestors",
    }

    try:
        response = requests.get(
            f"{CONFLUENCE_BASE_URL}/wiki/rest/api/content/search",
            headers=get_confluence_auth_headers(),
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            return format_error(response.status_code, response.text)

        data = response.json()
        results = []

        for item in data.get("results", []):
            links = item.get("_links", {})
            base_url = data.get("_links", {}).get("base", "")
            web_ui = links.get("webui", "")

            results.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "type": item.get("type"),
                "status": item.get("status"),
                "space_key": item.get("space", {}).get("key"),
                "space_name": item.get("space", {}).get("name"),
                "url": f"{base_url}{web_ui}" if web_ui else None,
                "updated": item.get("version", {}).get("when"),
                "author": item.get("version", {}).get("by", {}).get("displayName"),
                "excerpt": item.get("excerpt"),
            })

        return {
            "cql": cql,
            "total": data.get("totalSize", len(results)),
            "count": len(results),
            "results": results,
        }

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("search")
@click.argument("query")
@click.option("--space", help="Limit to a specific space key")
@click.option("--type", "content_type", type=click.Choice(["page", "blogpost", "comment"]), default="page")
@click.option("--max-results", default=25, type=int)
@click.pass_context
def search_cmd(ctx, query, space, content_type, max_results):
    """Search Confluence pages."""
    result = search_confluence(query, space, content_type, max_results)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
