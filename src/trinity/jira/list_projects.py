#!/usr/bin/env python3
"""List visible Jira projects."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_jira_auth_headers, JIRA_BASE_URL, format_error


def list_jira_projects(search: Optional[str] = None, max_results: int = 50) -> dict:
    """List all visible Jira projects, optionally filtered by name/key."""
    params: dict = {"maxResults": max_results, "expand": "description"}
    if search:
        params["query"] = search

    try:
        response = requests.get(
            f"{JIRA_BASE_URL}/rest/api/3/project/search",
            headers=get_jira_auth_headers(),
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            return format_error(response.status_code, response.text)

        data = response.json()
        projects = [
            {
                "key": p.get("key"),
                "name": p.get("name"),
                "id": p.get("id"),
                "project_type": p.get("projectTypeKey"),
                "description": p.get("description"),
                "lead": p.get("lead", {}).get("displayName") if p.get("lead") else None,
            }
            for p in data.get("values", [])
        ]

        return {"count": len(projects), "total": data.get("total", len(projects)), "projects": projects}

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("projects")
@click.option("--search", help="Filter by name or key")
@click.option("--max-results", default=50, type=int)
@click.pass_context
def projects_cmd(ctx, search, max_results):
    """List visible Jira projects."""
    result = list_jira_projects(search, max_results)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
