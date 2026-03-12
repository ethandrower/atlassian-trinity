#!/usr/bin/env python3
"""List sprints for a Jira Agile board."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_jira_auth_headers, AGILE_BASE_URL, format_error


def get_sprints(board_id: int, state: Optional[str] = None, max_results: int = 50) -> dict:
    """List sprints for a board. State: active | closed | future."""
    params: dict = {"maxResults": min(max_results, 100)}
    if state:
        params["state"] = state

    try:
        response = requests.get(
            f"{AGILE_BASE_URL}/board/{board_id}/sprint",
            headers=get_jira_auth_headers(),
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            return format_error(response.status_code, response.text)

        data = response.json()
        sprints = [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "state": s.get("state"),
                "start_date": s.get("startDate"),
                "end_date": s.get("endDate"),
                "complete_date": s.get("completeDate"),
                "goal": s.get("goal"),
            }
            for s in data.get("values", [])
        ]

        return {"board_id": board_id, "count": len(sprints), "sprints": sprints}

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


def get_active_sprint(board_id: int) -> dict:
    """Get the currently active sprint for a board."""
    result = get_sprints(board_id, state="active", max_results=1)
    if result.get("error"):
        return result
    if result.get("sprints"):
        return {"found": True, "sprint": result["sprints"][0]}
    return {"found": False, "message": "No active sprint found"}


@click.command("sprints")
@click.argument("board_id", type=int)
@click.option("--state", type=click.Choice(["active", "closed", "future"]))
@click.option("--active", "active_only", is_flag=True, help="Get active sprint only")
@click.option("--max-results", default=50, type=int)
@click.pass_context
def sprints_cmd(ctx, board_id, state, active_only, max_results):
    """List sprints for a Jira board."""
    if active_only:
        result = get_active_sprint(board_id)
    else:
        result = get_sprints(board_id, state, max_results)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
