#!/usr/bin/env python3
"""List Jira Agile boards."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_jira_auth_headers, AGILE_BASE_URL, format_error


def get_boards(
    project_key: Optional[str] = None,
    board_type: Optional[str] = None,
    max_results: int = 50,
) -> dict:
    """List Jira Agile (Scrum/Kanban) boards."""
    params: dict = {"maxResults": min(max_results, 100)}
    if project_key:
        params["projectKeyOrId"] = project_key
    if board_type:
        params["type"] = board_type

    try:
        response = requests.get(
            f"{AGILE_BASE_URL}/board",
            headers=get_jira_auth_headers(),
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            return format_error(response.status_code, response.text)

        data = response.json()
        boards = [
            {
                "id": b.get("id"),
                "name": b.get("name"),
                "type": b.get("type"),
                "project_key": b.get("location", {}).get("projectKey") if b.get("location") else None,
            }
            for b in data.get("values", [])
        ]

        return {"total": data.get("total", len(boards)), "count": len(boards), "boards": boards}

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("boards")
@click.option("--project", help="Filter by project key")
@click.option("--type", "board_type", type=click.Choice(["scrum", "kanban"]))
@click.option("--max-results", default=50, type=int)
@click.pass_context
def boards_cmd(ctx, project, board_type, max_results):
    """List Jira Agile boards."""
    result = get_boards(project, board_type, max_results)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
