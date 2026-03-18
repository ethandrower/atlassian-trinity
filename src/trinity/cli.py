#!/usr/bin/env python3
"""
Trinity — Unified Atlassian CLI
  trinity jira <command>        Jira Cloud REST API
  trinity bb <command>          Bitbucket Cloud REST API
  trinity confluence <command>  Confluence Cloud REST API
  trinity config                Manage credentials
"""

import json
import os
import sys
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

console = Console()


# ── Root group ─────────────────────────────────────────────────────────────────

@click.group()
@click.version_option(package_name="trinity-atlassian-cli")
@click.option("--json", "output_json", is_flag=True, help="JSON output (default for agent use)")
@click.option("--no-color", is_flag=True, help="Disable color output")
@click.pass_context
def cli(ctx, output_json, no_color):
    """Trinity — Unified Atlassian CLI for Jira, Confluence, and Bitbucket."""
    ctx.ensure_object(dict)
    ctx.obj["output_json"] = output_json
    ctx.obj["no_color"] = no_color
    if no_color:
        os.environ["NO_COLOR"] = "1"


# ── Jira subgroup ──────────────────────────────────────────────────────────────

@cli.group("jira")
@click.pass_context
def jira_group(ctx):
    """Jira Cloud commands."""
    pass


@jira_group.command("search")
@click.argument("jql")
@click.option("--max-results", default=50, type=int, help="Max results (default 50)")
@click.option("--fields", help="Comma-separated field list")
@click.pass_context
def jira_search(ctx, jql, max_results, fields):
    """Search Jira issues using JQL."""
    from .jira.search import search_jira
    field_list = fields.split(",") if fields else None
    result = search_jira(jql, max_results, field_list)

    if ctx.obj.get("output_json"):
        click.echo(json.dumps(result, indent=2))
    elif result.get("error"):
        console.print(f"[red]Error:[/red] {result['message']}")
    else:
        table = Table(title=f"Jira Search ({result['count']}/{result['total']})")
        table.add_column("Key", style="cyan")
        table.add_column("Summary", max_width=55)
        table.add_column("Status", style="green")
        table.add_column("Assignee", style="dim")
        table.add_column("Priority", style="yellow")
        for i in result["issues"]:
            table.add_row(i["key"] or "", (i["summary"] or "")[:55], i["status"] or "", i["assignee"] or "", i["priority"] or "")
        console.print(table)

    if result.get("error"):
        sys.exit(1)


@jira_group.command("show")
@click.argument("issue_key")
@click.option("--comments", "include_comments", is_flag=True)
@click.pass_context
def jira_show(ctx, issue_key, include_comments):
    """Show full details of a Jira issue."""
    from .jira.get_issue import get_jira_issue
    result = get_jira_issue(issue_key, include_comments=include_comments)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("comment")
@click.argument("issue_key")
@click.argument("text")
@click.option("--mention", nargs=2, multiple=True, metavar="ACCOUNT_ID NAME")
@click.pass_context
def jira_comment(ctx, issue_key, text, mention):
    """Add a comment to a Jira issue."""
    from .jira.add_comment import add_jira_comment
    mentions = [{"id": m[0], "name": m[1]} for m in mention] if mention else None
    result = add_jira_comment(issue_key, text, mentions)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("transition")
@click.argument("issue_key")
@click.argument("transition_name", required=False)
@click.option("--id", "transition_id", help="Transition ID")
@click.option("--comment", help="Comment during transition")
@click.pass_context
def jira_transition(ctx, issue_key, transition_name, transition_id, comment):
    """Transition a Jira issue to a new status."""
    from .jira.transition_issue import transition_jira_issue
    if not transition_name and not transition_id:
        raise click.UsageError("Provide a transition name or --id")
    result = transition_jira_issue(issue_key, transition_name, transition_id, comment=comment)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("edit")
@click.argument("issue_key")
@click.option("--assignee", help="Account ID")
@click.option("--priority", help="Priority name")
@click.option("--summary", help="New title")
@click.option("--labels", help="Comma-separated labels (replaces)")
@click.option("--add-labels", help="Labels to add")
@click.option("--remove-labels", help="Labels to remove")
@click.pass_context
def jira_edit(ctx, issue_key, assignee, priority, summary, labels, add_labels, remove_labels):
    """Update fields on a Jira issue."""
    from .jira.edit_issue import edit_jira_issue
    fields: dict = {}
    update: dict = {}
    if assignee:
        fields["assignee"] = None if assignee.lower() == "none" else {"accountId": assignee}
    if priority:
        fields["priority"] = {"name": priority}
    if summary:
        fields["summary"] = summary
    if labels:
        fields["labels"] = [l.strip() for l in labels.split(",")]
    if add_labels:
        update["labels"] = [{"add": l.strip()} for l in add_labels.split(",")]
    if remove_labels:
        update.setdefault("labels", []).extend([{"remove": l.strip()} for l in remove_labels.split(",")])
    if not fields and not update:
        raise click.UsageError("Provide at least one field to update")
    result = edit_jira_issue(issue_key, fields or None, update or None)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("transitions")
@click.argument("issue_key")
@click.pass_context
def jira_transitions(ctx, issue_key):
    """List available status transitions for a Jira issue."""
    from .jira.get_transitions import get_jira_transitions
    result = get_jira_transitions(issue_key)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("status-history")
@click.argument("issue_key")
@click.option("--target-status", help="Analyze a specific status")
@click.option("--all-transitions", is_flag=True)
@click.pass_context
def jira_status_history(ctx, issue_key, target_status, all_transitions):
    """Get status change history for a Jira issue."""
    from .jira.get_status_history import get_status_history
    result = get_status_history(issue_key, target_status, all_transitions)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("user")
@click.argument("query")
@click.option("--max-results", default=10, type=int)
@click.pass_context
def jira_user(ctx, query, max_results):
    """Look up a Jira user by name or email."""
    from .jira.lookup_user import lookup_jira_user
    result = lookup_jira_user(query, max_results)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("projects")
@click.option("--search", help="Filter by name or key")
@click.pass_context
def jira_projects(ctx, search):
    """List visible Jira projects."""
    from .jira.list_projects import list_jira_projects
    result = list_jira_projects(search)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("boards")
@click.option("--project", help="Filter by project key")
@click.option("--type", "board_type", type=click.Choice(["scrum", "kanban"]))
@click.pass_context
def jira_boards(ctx, project, board_type):
    """List Jira Agile boards."""
    from .jira.get_boards import get_boards
    result = get_boards(project, board_type)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("sprints")
@click.argument("board_id", type=int)
@click.option("--state", type=click.Choice(["active", "closed", "future"]))
@click.option("--active", "active_only", is_flag=True)
@click.pass_context
def jira_sprints(ctx, board_id, state, active_only):
    """List sprints for a Jira board."""
    from .jira.get_sprints import get_sprints, get_active_sprint
    if active_only:
        result = get_active_sprint(board_id)
    else:
        result = get_sprints(board_id, state)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("sprint-issues")
@click.argument("sprint_id", type=int)
@click.option("--status", help="Filter by status")
@click.option("--completed-only", is_flag=True)
@click.option("--max-results", default=100, type=int)
@click.pass_context
def jira_sprint_issues(ctx, sprint_id, status, completed_only, max_results):
    """Get issues in a Jira sprint."""
    from .jira.get_sprint_issues import get_sprint_issues, get_completed_sprint_issues
    if completed_only:
        result = get_completed_sprint_issues(sprint_id)
    else:
        result = get_sprint_issues(sprint_id, status, max_results=max_results)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("worklogs")
@click.argument("issue_key")
@click.option("--days", type=int)
@click.pass_context
def jira_worklogs(ctx, issue_key, days):
    """Get time-tracking worklogs for a Jira issue."""
    from datetime import datetime, timedelta, timezone
    from .jira.get_worklogs import get_issue_worklogs
    started_after = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    result = get_issue_worklogs(issue_key, started_after=started_after)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("issue-types")
@click.argument("project_key")
@click.pass_context
def jira_issue_types(ctx, project_key):
    """List available issue types for a project."""
    from .jira.create_issue import get_project_issue_types
    types = get_project_issue_types(project_key)
    if not types:
        click.echo(json.dumps({"error": True, "message": f"Could not fetch issue types for {project_key}"}))
        sys.exit(1)
    click.echo(json.dumps({"project": project_key, "issue_types": types}, indent=2))


@jira_group.command("create")
@click.option("--project", required=True, help="Project key (e.g. ECD)")
@click.option("--summary", required=True, help="Issue title")
@click.option("--type", "issue_type", default="Task",
              type=click.Choice(["Task", "Story", "Epic", "Bug", "Sub-task"], case_sensitive=False),
              help="Issue type (default: Task)")
@click.option("--description", help="Issue description (plain text)")
@click.option("--assignee", help="Assignee account ID")
@click.option("--priority", type=click.Choice(["Highest", "High", "Medium", "Low", "Lowest"]),
              help="Priority")
@click.option("--labels", help="Comma-separated labels")
@click.option("--parent", "parent_key", help="Parent issue key (for Sub-tasks, or Stories under an Epic in next-gen projects)")
@click.option("--epic", "epic_key", help="Epic key to link (classic projects — use --parent for next-gen)")
@click.option("--points", "story_points", type=float, help="Story points")
@click.option("--sprint", "sprint_id", type=int, help="Sprint ID to add the issue to")
@click.option("--fix-version", help="Fix version name")
@click.option("--components", help="Comma-separated component names")
@click.pass_context
def jira_create(ctx, project, summary, issue_type, description, assignee, priority,
                labels, parent_key, epic_key, story_points, sprint_id, fix_version, components):
    """Create a Jira issue (Task, Story, Epic, Bug, Sub-task)."""
    from .jira.create_issue import create_jira_issue
    result = create_jira_issue(
        project_key=project,
        summary=summary,
        issue_type=issue_type,
        description=description,
        assignee_id=assignee,
        priority=priority,
        labels=labels.split(",") if labels else None,
        parent_key=parent_key,
        epic_key=epic_key,
        story_points=story_points,
        sprint_id=sprint_id,
        fix_version=fix_version,
        components=components.split(",") if components else None,
    )
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("release-issues")
@click.option("--project", default="ECD")
@click.option("--days", default=14, type=int)
@click.option("--fix-version")
@click.option("--current-sprint", is_flag=True)
@click.pass_context
def jira_release_issues(ctx, project, days, fix_version, current_sprint):
    """Get completed Jira issues for release notes."""
    from .jira.get_release_issues import get_release_issues, get_current_sprint_completed
    if current_sprint:
        result = get_current_sprint_completed(project)
    else:
        result = get_release_issues(fix_version=fix_version, days=days, project=project)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


# ── Bitbucket subgroup ─────────────────────────────────────────────────────────

@cli.group("bb")
@click.option("--workspace", "-w", help="Override workspace")
@click.option("--repo", "-r", help="Override repo name")
@click.pass_context
def bb_group(ctx, workspace, repo):
    """Bitbucket Cloud commands."""
    ctx.ensure_object(dict)
    ctx.obj["bb_workspace"] = workspace or os.getenv("BITBUCKET_WORKSPACE", "")
    ctx.obj["bb_repo"] = repo


def _bb_context(ctx) -> tuple:
    """Resolve workspace and repo from context or git remote."""
    workspace = ctx.obj.get("bb_workspace")
    repo = ctx.obj.get("bb_repo")

    if not workspace or not repo:
        try:
            from git import Repo, InvalidGitRepositoryError
            import re
            git_repo = Repo(search_parent_directories=True)
            for remote in git_repo.remotes:
                for url in [u for u in [remote.url]]:
                    m = re.search(r"bitbucket\.org[:/]([^/]+)/([^/.]+)", url)
                    if m:
                        workspace = workspace or m.group(1)
                        repo = repo or m.group(2)
        except Exception:
            pass

    return workspace or "", repo or ""


@bb_group.command("list")
@click.option("--state", default="OPEN", help="OPEN|MERGED|DECLINED")
@click.option("--author", help="Filter by author")
@click.option("--limit", default=25, type=int)
@click.option("--all", "fetch_all", is_flag=True)
@click.pass_context
def bb_list(ctx, state, author, limit, fetch_all):
    """List pull requests."""
    from .bitbucket.api import BitbucketAPI
    from .bitbucket.commands import list_prs
    api = BitbucketAPI()
    workspace, repo = _bb_context(ctx)
    prs = list_prs(api, workspace, repo, state=state, author=author, limit=limit, fetch_all=fetch_all)

    if ctx.obj.get("output_json"):
        click.echo(json.dumps(prs, indent=2))
    else:
        if not prs:
            console.print("No pull requests found.", style="yellow")
            return
        table = Table(title=f"Pull Requests ({workspace}/{repo})")
        table.add_column("ID", style="cyan")
        table.add_column("Title", max_width=50)
        table.add_column("Author", style="green")
        table.add_column("State", style="magenta")
        table.add_column("Created", style="dim")
        for pr in prs:
            author_name = (pr.get("author", {}).get("display_name") or pr.get("author", {}).get("nickname") or "?")
            table.add_row(
                str(pr["id"]), (pr["title"][:50] + "...") if len(pr["title"]) > 50 else pr["title"],
                author_name, pr["state"], (pr.get("created_on") or "")[:10],
            )
        console.print(table)


@bb_group.command("show")
@click.argument("pr_id", type=int)
@click.option("--comments", "include_comments", is_flag=True)
@click.pass_context
def bb_show(ctx, pr_id, include_comments):
    """Show pull request details."""
    from .bitbucket.api import BitbucketAPI
    from .bitbucket.commands import show_pr
    api = BitbucketAPI()
    workspace, repo = _bb_context(ctx)
    result = show_pr(api, workspace, repo, pr_id, include_comments=include_comments)
    click.echo(json.dumps(result, indent=2))


@bb_group.command("comment")
@click.argument("pr_id", type=int)
@click.option("--message", "-m", required=True, help="Comment text")
@click.option("--file", help="File path for inline comment")
@click.option("--line", type=int, help="Line number")
@click.option("--reply-to", type=int, help="Reply to comment ID")
@click.pass_context
def bb_comment(ctx, pr_id, message, file, line, reply_to):
    """Add a comment to a pull request."""
    from .bitbucket.api import BitbucketAPI
    from .bitbucket.commands import comment_pr
    api = BitbucketAPI()
    workspace, repo = _bb_context(ctx)
    result = comment_pr(api, workspace, repo, pr_id, message, file=file, line=line, reply_to=reply_to)
    click.echo(json.dumps(result, indent=2))


@bb_group.command("diff")
@click.argument("pr_id", type=int)
@click.option("--stat", is_flag=True, help="Show diffstat instead of full diff")
@click.pass_context
def bb_diff(ctx, pr_id, stat):
    """Show PR diff or diffstat."""
    from .bitbucket.api import BitbucketAPI
    from .bitbucket.commands import diff_pr
    api = BitbucketAPI()
    workspace, repo = _bb_context(ctx)
    result = diff_pr(api, workspace, repo, pr_id, stat=stat)
    if isinstance(result, str):
        click.echo(result)
    else:
        click.echo(json.dumps(result, indent=2))


@bb_group.command("activity")
@click.argument("pr_id", type=int)
@click.option("--limit", default=50, type=int)
@click.pass_context
def bb_activity(ctx, pr_id, limit):
    """Show PR activity timeline."""
    from .bitbucket.api import BitbucketAPI
    from .bitbucket.commands import activity_pr
    api = BitbucketAPI()
    workspace, repo = _bb_context(ctx)
    result = activity_pr(api, workspace, repo, pr_id, limit=limit)
    click.echo(json.dumps(result, indent=2))


# ── Confluence subgroup ────────────────────────────────────────────────────────

@cli.group("confluence")
@click.pass_context
def confluence_group(ctx):
    """Confluence Cloud commands."""
    pass


@confluence_group.command("search")
@click.argument("query")
@click.option("--space", help="Limit to space key")
@click.option("--type", "content_type", default="page", type=click.Choice(["page", "blogpost"]))
@click.option("--max-results", default=25, type=int)
@click.pass_context
def confluence_search(ctx, query, space, content_type, max_results):
    """Search Confluence pages."""
    from .confluence.search import search_confluence
    result = search_confluence(query, space, content_type, max_results)

    if ctx.obj.get("output_json"):
        click.echo(json.dumps(result, indent=2))
    elif result.get("error"):
        console.print(f"[red]Error:[/red] {result['message']}")
        sys.exit(1)
    else:
        table = Table(title=f"Confluence Search ({result['count']}/{result['total']})")
        table.add_column("ID", style="cyan")
        table.add_column("Title", max_width=55)
        table.add_column("Space", style="green")
        table.add_column("Updated", style="dim")
        for r in result["results"]:
            table.add_row(r["id"] or "", r["title"][:55], r["space_key"] or "", (r.get("updated") or "")[:10])
        console.print(table)


@confluence_group.command("get")
@click.argument("page_id")
@click.option("--no-body", is_flag=True)
@click.option("--ancestors", is_flag=True)
@click.pass_context
def confluence_get(ctx, page_id, no_body, ancestors):
    """Get a Confluence page by ID."""
    from .confluence.get_page import get_confluence_page
    result = get_confluence_page(page_id, include_body=not no_body, include_ancestors=ancestors)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@confluence_group.command("spaces")
@click.option("--search", help="Filter by name or key")
@click.pass_context
def confluence_spaces(ctx, search):
    """List Confluence spaces."""
    from .confluence.get_spaces import get_confluence_spaces
    result = get_confluence_spaces(search)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@confluence_group.command("children")
@click.argument("page_id")
@click.pass_context
def confluence_children(ctx, page_id):
    """List child pages of a Confluence page."""
    from .confluence.get_children import get_page_children
    result = get_page_children(page_id)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@confluence_group.command("pages")
@click.argument("space_key")
@click.option("--max-results", default=None, type=int, help="Cap total results (default: all)")
@click.option("--limit", default=50, type=int, help="API page size (max 50)")
@click.pass_context
def confluence_pages(ctx, space_key, max_results, limit):
    """List all pages in a Confluence space."""
    from .confluence.list_space_pages import list_space_pages
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


@confluence_group.command("create")
@click.option("--space", required=True, help="Space key")
@click.option("--title", required=True, help="Page title")
@click.option("--body", help="Page body (HTML storage format)")
@click.option("--body-file", type=click.Path(exists=True))
@click.option("--parent", help="Parent page ID")
@click.pass_context
def confluence_create(ctx, space, title, body, body_file, parent):
    """Create a new Confluence page."""
    from .confluence.create_page import create_confluence_page
    if body_file:
        with open(body_file) as f:
            body = f.read()
    if not body:
        raise click.UsageError("Provide --body or --body-file")
    result = create_confluence_page(space, title, body, parent)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@confluence_group.command("update")
@click.argument("page_id")
@click.option("--title", help="New title")
@click.option("--body", help="New body")
@click.option("--body-file", type=click.Path(exists=True))
@click.option("--comment", help="Version comment")
@click.pass_context
def confluence_update(ctx, page_id, title, body, body_file, comment):
    """Update a Confluence page."""
    from .confluence.update_page import update_confluence_page
    if body_file:
        with open(body_file) as f:
            body = f.read()
    if not title and not body:
        raise click.UsageError("Provide --title or --body / --body-file")
    result = update_confluence_page(page_id, title=title, body=body, version_comment=comment)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@confluence_group.command("comment")
@click.argument("page_id")
@click.argument("text")
@click.pass_context
def confluence_comment(ctx, page_id, text):
    """Add a comment to a Confluence page."""
    from .confluence.add_comment import add_confluence_comment
    result = add_confluence_comment(page_id, text)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


# ── Config command ─────────────────────────────────────────────────────────────

@cli.command("config")
@click.option("--email", help="Atlassian account email")
@click.option("--token", help="Atlassian API token")
@click.option("--cloud-id", help="Atlassian Cloud ID")
@click.option("--jira-url", help="Jira instance URL (e.g., https://co.atlassian.net)")
@click.option("--bb-token", help="Bitbucket repo access token")
@click.option("--bb-workspace", help="Default Bitbucket workspace")
@click.option("--list", "list_config", is_flag=True, help="Show current config")
@click.option("--reset", is_flag=True, help="Reset to defaults")
def config(email, token, cloud_id, jira_url, bb_token, bb_workspace, list_config, reset):
    """Manage Trinity credentials."""
    from .base.auth import load_config, save_config

    if reset:
        from .base.auth import DEFAULT_CONFIG
        save_config(DEFAULT_CONFIG.copy())
        console.print("[green]Config reset to defaults.[/green]")
        return

    cfg = load_config()

    if list_config:
        display = json.loads(json.dumps(cfg))
        # Mask tokens
        if display.get("atlassian", {}).get("api_token"):
            display["atlassian"]["api_token"] = "***"
        if display.get("bitbucket", {}).get("repo_token"):
            display["bitbucket"]["repo_token"] = "***"
        click.echo(json.dumps(display, indent=2))
        return

    if email:
        cfg["atlassian"]["email"] = email
    if token:
        cfg["atlassian"]["api_token"] = token
    if cloud_id:
        cfg["atlassian"]["cloud_id"] = cloud_id
    if jira_url:
        cfg["atlassian"]["jira_url"] = jira_url
    if bb_token:
        cfg["bitbucket"]["repo_token"] = bb_token
    if bb_workspace:
        cfg["bitbucket"]["workspace"] = bb_workspace

    if any([email, token, cloud_id, jira_url, bb_token, bb_workspace]):
        save_config(cfg)
        console.print("[green]Config saved.[/green]")
    else:
        console.print("Use options to set values. Run [cyan]trinity config --help[/cyan] for details.")


def main():
    """CLI entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        sys.exit(1)


if __name__ == "__main__":
    main()
