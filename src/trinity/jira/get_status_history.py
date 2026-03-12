#!/usr/bin/env python3
"""Get status change history and time-in-status for a Jira issue."""

import json
import sys
from datetime import datetime
from typing import Dict, List, Optional

import click
import requests
from dateutil import parser as date_parser

from ..base import get_jira_auth_headers, JIRA_BASE_URL, format_error


def get_status_history(
    issue_key: str,
    target_status: Optional[str] = None,
    all_transitions: bool = False,
) -> dict:
    """
    Get status change history for a Jira issue.

    Returns current status, time in current status, and optionally
    full transition history or analysis of a specific target status.
    """
    try:
        response = requests.get(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}",
            headers=get_jira_auth_headers(),
            params={"expand": "changelog"},
            timeout=30,
        )

        if response.status_code != 200:
            return format_error(response.status_code, response.text)

        data = response.json()
        fields = data.get("fields", {})
        changelog = data.get("changelog", {})

        current_status = fields.get("status", {}).get("name")
        current_status_category = fields.get("status", {}).get("statusCategory", {}).get("name")

        status_transitions = []
        for history in changelog.get("histories", []):
            created = history.get("created")
            author = history.get("author", {}).get("displayName", "Unknown")
            for item in history.get("items", []):
                if item.get("field") == "status":
                    status_transitions.append({
                        "from_status": item.get("fromString"),
                        "to_status": item.get("toString"),
                        "changed_at": created,
                        "changed_by": author,
                    })

        status_transitions.sort(key=lambda x: x["changed_at"])

        entered_current_status = None
        for t in reversed(status_transitions):
            if t["to_status"] == current_status:
                entered_current_status = t["changed_at"]
                break

        if not entered_current_status:
            entered_current_status = fields.get("created")

        time_in_current_status_hours = None
        if entered_current_status:
            try:
                entered_dt = date_parser.parse(entered_current_status)
            except Exception:
                entered_dt = datetime.fromisoformat(entered_current_status.replace("Z", "+00:00"))
            delta = datetime.now(entered_dt.tzinfo) - entered_dt
            time_in_current_status_hours = delta.total_seconds() / 3600

        result = {
            "issue_key": issue_key,
            "current_status": current_status,
            "current_status_category": current_status_category,
            "entered_current_status": entered_current_status,
            "time_in_current_status_hours": round(time_in_current_status_hours, 2) if time_in_current_status_hours else None,
            "time_in_current_status_days": round(time_in_current_status_hours / 24, 2) if time_in_current_status_hours else None,
        }

        if all_transitions:
            result["status_history"] = status_transitions

        if target_status:
            target_info = _find_target_status_info(
                status_transitions, target_status, current_status, entered_current_status
            )
            if target_info:
                result["target_status_info"] = target_info

        return result

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


def _find_target_status_info(
    transitions: List[Dict],
    target_status: str,
    current_status: str,
    current_status_entry: str,
) -> Optional[Dict]:
    entered_at = None
    exited_at = None

    for i, t in enumerate(reversed(transitions)):
        reversed_index = len(transitions) - 1 - i
        if t["to_status"] == target_status:
            entered_at = t["changed_at"]
            for j in range(reversed_index + 1, len(transitions)):
                if transitions[j]["from_status"] == target_status:
                    exited_at = transitions[j]["changed_at"]
                    break
            break

    if not entered_at:
        return None

    try:
        entered_dt = date_parser.parse(entered_at)
    except Exception:
        entered_dt = datetime.fromisoformat(entered_at.replace("Z", "+00:00"))

    if target_status == current_status:
        exited_dt = datetime.now(entered_dt.tzinfo)
        still_in_status = True
    elif exited_at:
        try:
            exited_dt = date_parser.parse(exited_at)
        except Exception:
            exited_dt = datetime.fromisoformat(exited_at.replace("Z", "+00:00"))
        still_in_status = False
    else:
        exited_dt = datetime.now(entered_dt.tzinfo)
        still_in_status = False

    hours = (exited_dt - entered_dt).total_seconds() / 3600
    return {
        "status": target_status,
        "entered_at": entered_at,
        "exited_at": exited_at if not still_in_status else None,
        "still_in_status": still_in_status,
        "hours_in_status": round(hours, 2),
        "days_in_status": round(hours / 24, 2),
    }


@click.command("status-history")
@click.argument("issue_key")
@click.option("--target-status", help="Analyze a specific status")
@click.option("--all-transitions", is_flag=True, help="Include full transition history")
@click.pass_context
def status_history_cmd(ctx, issue_key, target_status, all_transitions):
    """Get status history and time-in-status for a Jira issue."""
    result = get_status_history(issue_key, target_status, all_transitions)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
