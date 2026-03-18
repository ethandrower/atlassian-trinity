#!/usr/bin/env python3
"""List all pages in a Confluence space with full pagination."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_confluence_auth_headers, CONFLUENCE_BASE_URL, format_error


def list_space_pages(
    space_key: str,
    expand: str = "version,ancestors",
    limit: int = 50,
    max_results: Optional[int] = None,
) -> dict:
    """
    Return all pages in a Confluence space, handling pagination automatically.

    Uses the v1 content API with offset-based pagination. The v1 API is
    preferred over v2 because it supports spaceKey lookup directly and
    returns totalSize reliably.

    Args:
        space_key: Confluence space key (e.g. "ECD", "DOCS")
        expand: Comma-separated list of properties to expand on each page.
                Defaults to "version,ancestors" which is sufficient for
                building page trees and incremental sync checks.
        limit: Page size per API request (max 50 for this endpoint).
        max_results: Cap total results returned. None = fetch all pages.

    Returns:
        dict: {
            "space_key": str,
            "count": int,
            "pages": [
                {
                    "id": str,
                    "title": str,
                    "status": str,
                    "version": int,
                    "ancestors": [{"id": str, "title": str}],
                    "updated": str (ISO 8601),
                    "author": str,
                    "url": str,
                }
            ]
        }
    """
    limit = min(limit, 50)
    start = 0
    all_pages = []
    base_url = None

    while True:
        params = {
            "spaceKey": space_key,
            "type": "page",
            "status": "current",
            "expand": expand,
            "start": start,
            "limit": limit,
        }

        try:
            response = requests.get(
                f"{CONFLUENCE_BASE_URL}/wiki/rest/api/content",
                headers=get_confluence_auth_headers(),
                params=params,
                timeout=30,
            )
        except requests.exceptions.Timeout:
            return format_error(408, "Request timed out")
        except requests.exceptions.RequestException as e:
            return format_error(500, str(e))

        if response.status_code != 200:
            return format_error(response.status_code, response.text)

        data = response.json()

        if base_url is None:
            base_url = data.get("_links", {}).get("base", "")

        results = data.get("results", [])
        for page in results:
            links = page.get("_links", {})
            ancestors = [
                {"id": a.get("id"), "title": a.get("title")}
                for a in page.get("ancestors", [])
            ]
            all_pages.append({
                "id": page.get("id"),
                "title": page.get("title"),
                "status": page.get("status"),
                "version": page.get("version", {}).get("number", 1),
                "ancestors": ancestors,
                "updated": page.get("version", {}).get("when"),
                "author": page.get("version", {}).get("by", {}).get("displayName"),
                "url": f"{base_url}{links.get('webui', '')}" if links.get("webui") else None,
            })

            if max_results and len(all_pages) >= max_results:
                break

        if max_results and len(all_pages) >= max_results:
            all_pages = all_pages[:max_results]
            break

        # Stop when we get fewer results than requested — no more pages
        if len(results) < limit:
            break

        start += len(results)

    return {
        "space_key": space_key,
        "count": len(all_pages),
        "pages": all_pages,
    }


@click.command("pages")
@click.argument("space_key")
@click.option("--max-results", default=None, type=int, help="Cap total results (default: all)")
@click.option("--limit", default=50, type=int, help="API page size (max 50)")
@click.pass_context
def pages_cmd(ctx, space_key, max_results, limit):
    """List all pages in a Confluence space."""
    result = list_space_pages(space_key, limit=limit, max_results=max_results)

    if ctx.obj and ctx.obj.get("output_json"):
        click.echo(json.dumps(result, indent=2))
    elif result.get("error"):
        click.echo(f"Error: {result['message']}", err=True)
        sys.exit(1)
    else:
        click.echo(f"Space: {result['space_key']}  ({result['count']} pages)")
        for page in result["pages"]:
            depth = len(page.get("ancestors", []))
            indent = "  " * depth
            click.echo(f"{indent}{page['id']}  {page['title']}  (v{page['version']})")
