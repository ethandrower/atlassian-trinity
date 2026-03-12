#!/usr/bin/env python3
"""Transition a Jira issue to a new status."""

import json
import sys
from typing import Optional

import click
import requests

from ..base import get_jira_auth_headers, JIRA_BASE_URL, format_error
from .get_transitions import get_jira_transitions


def transition_jira_issue(
    issue_key: str,
    transition_name: Optional[str] = None,
    transition_id: Optional[str] = None,
    fields: Optional[dict] = None,
    comment: Optional[str] = None,
) -> dict:
    """Transition a Jira issue to a new status by name or ID."""
    if not transition_id and not transition_name:
        return format_error(400, "Either transition_name or transition_id is required")

    if not transition_id:
        transitions = get_jira_transitions(issue_key)
        if transitions.get("error"):
            return transitions

        matched = next(
            (t for t in transitions.get("transitions", [])
             if t["name"].lower() == transition_name.lower()
             or t["to_status"].lower() == transition_name.lower()),
            None,
        )

        if not matched:
            available = [f"{t['name']} -> {t['to_status']}" for t in transitions.get("transitions", [])]
            return format_error(
                400,
                f"Transition '{transition_name}' not available. "
                f"Current: {transitions.get('current_status')}. "
                f"Available: {', '.join(available)}",
            )

        transition_id = matched["id"]

    payload: dict = {"transition": {"id": str(transition_id)}}
    if fields:
        payload["fields"] = fields
    if comment:
        payload["update"] = {
            "comment": [{"add": {"body": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}],
            }}}]
        }

    try:
        response = requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions",
            headers=get_jira_auth_headers(),
            json=payload,
            timeout=30,
        )

        if response.status_code == 204:
            new_resp = requests.get(
                f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}",
                headers=get_jira_auth_headers(),
                params={"fields": "status"},
                timeout=30,
            )
            new_status = None
            if new_resp.status_code == 200:
                new_status = new_resp.json().get("fields", {}).get("status", {}).get("name")
            return {
                "success": True,
                "issue_key": issue_key,
                "transition_id": transition_id,
                "new_status": new_status,
            }

        return format_error(response.status_code, response.text)

    except requests.exceptions.Timeout:
        return format_error(408, "Request timed out")
    except requests.exceptions.RequestException as e:
        return format_error(500, str(e))


@click.command("transition")
@click.argument("issue_key")
@click.argument("transition", required=False)
@click.option("--id", "transition_id", help="Transition ID (overrides name)")
@click.option("--comment", help="Comment to add during transition")
@click.pass_context
def transition_cmd(ctx, issue_key, transition, transition_id, comment):
    """Transition a Jira issue to a new status."""
    if not transition and not transition_id:
        raise click.UsageError("Provide a transition name or --id")
    result = transition_jira_issue(issue_key, transition, transition_id, comment=comment)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)
