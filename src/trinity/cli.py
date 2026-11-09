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

from .base.exceptions import ConfigurationError, TrinityError

console = Console()


def _wants_json(explicit: Optional[bool] = None) -> bool:
    """JSON unless asked otherwise or a person is reading a terminal.

    Agents and scripts read Trinity through a pipe. Tables cut off long titles
    there, and nothing can parse them.
    """
    if explicit is not None:
        return explicit
    return not sys.stdout.isatty()


class RootGroup(click.Group):
    """Accept --json / --table anywhere, not only before the subcommand."""

    def parse_args(self, ctx, args):
        end = args.index("--") if "--" in args else len(args)
        flags = [a for a in args[:end] if a in ("--json", "--table")]
        rest = [a for a in args[:end] if a not in ("--json", "--table")]
        return super().parse_args(ctx, flags + rest + args[end:])


class LoginCheckedCommand(click.Command):
    """Confirm the Atlassian login works before running the command.

    Jira treats a rejected login as an anonymous visitor, so without this a bad
    token reads as "that issue does not exist" or as an empty search. Runs here
    rather than in the group callback so --help and usage errors stay offline.
    """

    def invoke(self, ctx):
        from .base.health import require_atlassian_login
        require_atlassian_login()
        return super().invoke(ctx)


class AtlassianGroup(click.Group):
    command_class = LoginCheckedCommand


# ── Root group ─────────────────────────────────────────────────────────────────

@click.group(cls=RootGroup, epilog="""\b
Start here:
  trinity doctor                  Check every login and repo token
  trinity jira show PROJ-123      Read a ticket
  trinity bb -r my-repo list      List open pull requests

\b
Output is JSON when piped and a table in a terminal. --json or --table forces it.
Every error exits non-zero. JSON errors look like {"error": true, "message": "..."}.
Each command has examples, e.g. trinity jira search --help
Full docs: README.md and docs/ at https://github.com/ethandrower/atlassian-trinity
""")
@click.version_option(package_name="trinity-atlassian-cli")
@click.option("--json/--table", "output_json", default=None,
              help="Force JSON or table output, anywhere on the line. "
                   "Default: JSON when piped, table in a terminal.")
@click.option("--no-color", is_flag=True, help="Disable color output")
@click.pass_context
def cli(ctx, output_json, no_color):
    """Trinity — Unified Atlassian CLI for Jira, Confluence, and Bitbucket."""
    ctx.ensure_object(dict)
    ctx.obj["output_json"] = _wants_json(output_json)
    ctx.obj["no_color"] = no_color
    if no_color:
        os.environ["NO_COLOR"] = "1"


# ── Jira subgroup ──────────────────────────────────────────────────────────────

@cli.group("jira", cls=AtlassianGroup)
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
    """Search Jira issues using JQL.

    \b
    Examples:
      trinity jira search "project = PROJ AND status = 'In Progress'"
      trinity jira search "assignee = currentUser()" --max-results 10 --fields summary,status
    """
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
    """Show full details of a Jira issue.

    \b
    Examples:
      trinity jira show PROJ-123
      trinity jira show PROJ-123 --comments
    """
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
    """Add a comment to a Jira issue.

    \b
    Examples:
      trinity jira comment PROJ-123 "Ready for QA"
    """
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
@click.option("--team", "team_id", help="Team id for the Team field ('none' clears it)")
@click.pass_context
def jira_edit(ctx, issue_key, assignee, priority, summary, labels, add_labels, remove_labels, team_id):
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
    if team_id:
        from .jira.create_issue import TEAM_FIELD
        fields[TEAM_FIELD] = None if team_id.lower() == "none" else team_id
    if not fields and not update:
        raise click.UsageError("Provide at least one field to update")
    result = edit_jira_issue(issue_key, fields or None, update or None)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("link")
@click.argument("source")
@click.argument("relation")
@click.argument("target")
@click.option("--comment", help="Comment to add alongside the link")
@click.pass_context
def jira_link(ctx, source, relation, target, comment):
    """Link two issues: SOURCE RELATION TARGET, e.g. ECD-1 duplicates ECD-2.

    RELATION is a link phrase in either direction ("blocks", "is blocked by",
    "duplicates", "relates to") or a type name. See `trinity jira link-types`.
    """
    from .jira.link_issues import link_jira_issues
    result = link_jira_issues(source, relation, target, comment=comment)
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


@jira_group.command("link-types")
@click.pass_context
def jira_link_types(ctx):
    """List the issue link types and their phrases."""
    from .jira.link_issues import get_link_types
    result = get_link_types()
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
              help="Issue type as the project defines it, e.g. Task, Story, Bug, Incident, "
                   "Hotfix (default: Task). `trinity jira issue-types <PROJECT>` lists them.")
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
@click.option("--team", "team_id", help="Team id (default: the project's jira.default_team from config)")
@click.option("--no-team", is_flag=True, help="Don't set the project's default Team")
@click.pass_context
def jira_create(ctx, project, summary, issue_type, description, assignee, priority,
                labels, parent_key, epic_key, story_points, sprint_id, fix_version, components,
                team_id, no_team):
    """Create a Jira issue of any type the project defines."""
    from .jira.create_issue import create_jira_issue, resolve_issue_type

    # Refuse a silent substitution. An unmatched type otherwise falls back to
    # the project's first type, so asking for an Incident and being handed a
    # Task would look like success and the caller would never know.
    resolved, available = resolve_issue_type(issue_type, project)
    if available and resolved.lower() != issue_type.lower():
        raise click.ClickException(
            f"{project} has no issue type {issue_type!r}. Available: {', '.join(available)}"
        )

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
        team_id=team_id,
        use_default_team=not no_team,
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
@click.option("--repo", "-r", help="Repo name. Goes before the subcommand: trinity bb -r my-repo list")
@click.pass_context
def bb_group(ctx, workspace, repo):
    """Bitbucket Cloud commands.

    The repo comes from -r, then the git remote of the current directory, then
    bitbucket.default_repo in the config.
    """
    ctx.ensure_object(dict)
    ctx.obj["bb_workspace"] = workspace or os.getenv("BITBUCKET_WORKSPACE", "")
    ctx.obj["bb_repo"] = repo


def _bb_context(ctx) -> tuple:
    """Resolve workspace and repo from flags, git remote, then config."""
    from .base.auth import load_config
    from .base.repo_context import resolve_workspace_repo

    workspace, repo = resolve_workspace_repo(
        ctx.obj.get("bb_workspace"),
        ctx.obj.get("bb_repo"),
    )
    if not repo:
        # Without this the URL has an empty repo, no per-repo token matches, and
        # Bitbucket's 401 reads as a bad token rather than a missing repo name.
        known = sorted((load_config().get("bitbucket") or {}).get("repo_tokens") or {})
        raise ConfigurationError(
            "No Bitbucket repo given, and none could be worked out from this directory. "
            "Pass -r before the subcommand: trinity bb -r REPO list"
            + (f". Configured repos: {', '.join(known)}" if known else "")
        )
    return workspace, repo


@bb_group.command("list")
@click.option("--state", default="OPEN", help="OPEN|MERGED|DECLINED")
@click.option("--author", help="Filter by author")
@click.option("--limit", default=25, type=int)
@click.option("--all", "fetch_all", is_flag=True)
@click.pass_context
def bb_list(ctx, state, author, limit, fetch_all):
    """List pull requests.

    \b
    Examples:
      trinity bb -r my-repo list
      trinity bb -r my-repo list --state MERGED --limit 10
    """
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
    """Show pull request details.

    \b
    Examples:
      trinity bb -r my-repo show 42 --comments
    """
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
    """Add a comment to a pull request.

    \b
    Examples:
      trinity bb -r my-repo comment 42 -m "Looks good"
      trinity bb -r my-repo comment 42 -m "Null check?" --file src/app.py --line 10
    """
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
    """Show PR diff or diffstat.

    \b
    Examples:
      trinity bb -r my-repo diff 42 --stat
    """
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


@bb_group.command("create")
@click.option("--title", "-t", required=True, help="PR title")
@click.option("--description", "-d", default="", help="PR description (markdown)")
@click.option("--description-file", type=click.Path(exists=True, dir_okay=False),
              help="Read description from file (overrides --description)")
@click.option("--source", "-s", help="Source branch (default: current git branch)")
@click.option("--dest", default="dev", help="Destination branch (default: dev)")
@click.option("--reviewer", "reviewer", multiple=True,
              help="Reviewer: account UUID {...}, nickname, or alias from config. Repeatable.")
@click.option("--reviewers", help="Comma-separated reviewers (same forms as --reviewer)")
@click.option("--close-branch", is_flag=True, help="Close source branch on merge")
@click.option("--draft", is_flag=True, help="Open as a draft PR (not ready for review)")
@click.option("--web", is_flag=True, help="Open the created PR in a browser")
@click.pass_context
def bb_create(ctx, title, description, description_file, source, dest, reviewer, reviewers,
              close_branch, draft, web):
    """Create a pull request.

    \b
    Examples:
      trinity bb -r my-repo create -t "Fix login" --description-file body.md -s my-branch --dest main --draft
      trinity bb -r my-repo create -t "Fix login" -s my-branch --reviewer devbot --reviewer joshua

    The PR author is never added as a reviewer (Bitbucket rejects it).
    """
    from .bitbucket.api import BitbucketAPI
    from .bitbucket.commands import create_pr
    if description_file:
        with open(description_file) as f:
            description = f.read()
    api = BitbucketAPI()
    workspace, repo = _bb_context(ctx)
    result = create_pr(
        api, workspace, repo,
        title=title, description=description,
        source=source, dest=dest,
        reviewers=list(reviewer) + ([reviewers] if reviewers else []),
        close_branch=close_branch, draft=draft, web=web,
    )
    if ctx.obj.get("output_json"):
        click.echo(json.dumps(result, indent=2))
    else:
        pr_id = result.get("id")
        html_url = result.get("links", {}).get("html", {}).get("href", "")
        label = "draft PR" if result.get("draft") else "PR"
        console.print(f"[green]{label} #{pr_id} created:[/green] {html_url}")
        _print_reviewers(result.get("reviewers") or [])


@bb_group.command("merge")
@click.argument("pr_id", type=int)
@click.option("--strategy",
              type=click.Choice(["merge_commit", "squash", "fast_forward"]),
              default="merge_commit", help="Merge strategy")
@click.option("--message", "-m", help="Merge commit message")
@click.option("--close-branch", is_flag=True, help="Close source branch after merge")
@click.pass_context
def bb_merge(ctx, pr_id, strategy, message, close_branch):
    """Merge a pull request."""
    from .bitbucket.api import BitbucketAPI
    from .bitbucket.commands import merge_pr
    api = BitbucketAPI()
    workspace, repo = _bb_context(ctx)
    result = merge_pr(api, workspace, repo, pr_id, strategy=strategy,
                      message=message, close_branch=close_branch)
    if ctx.obj.get("output_json"):
        click.echo(json.dumps(result, indent=2))
    else:
        console.print(f"[green]PR #{pr_id} merged[/green] ({strategy})")


@bb_group.command("approve")
@click.argument("pr_id", type=int)
@click.pass_context
def bb_approve(ctx, pr_id):
    """Approve a pull request."""
    from .bitbucket.api import BitbucketAPI
    from .bitbucket.commands import approve_pr
    api = BitbucketAPI()
    workspace, repo = _bb_context(ctx)
    result = approve_pr(api, workspace, repo, pr_id)
    if ctx.obj.get("output_json"):
        click.echo(json.dumps(result, indent=2))
    else:
        console.print(f"[green]PR #{pr_id} approved[/green]")


@bb_group.command("decline")
@click.argument("pr_id", type=int)
@click.pass_context
def bb_decline(ctx, pr_id):
    """Decline a pull request."""
    from .bitbucket.api import BitbucketAPI
    from .bitbucket.commands import decline_pr
    api = BitbucketAPI()
    workspace, repo = _bb_context(ctx)
    result = decline_pr(api, workspace, repo, pr_id)
    if ctx.obj.get("output_json"):
        click.echo(json.dumps(result, indent=2))
    else:
        console.print(f"[yellow]PR #{pr_id} declined[/yellow]")


@bb_group.command("update")
@click.argument("pr_id", type=int)
@click.option("--title", help="New title")
@click.option("--description", help="New description")
@click.option("--description-file", type=click.Path(exists=True, dir_okay=False),
              help="Read description from file")
@click.option("--dest", help="New destination branch")
@click.option("--reviewer", "add_reviewers", multiple=True,
              help="Add a reviewer (UUID {...}, nickname, or alias). Repeatable. "
                   "Existing reviewers are kept.")
@click.option("--remove-reviewer", "remove_reviewers", multiple=True,
              help="Remove a reviewer (same forms). Repeatable.")
@click.pass_context
def bb_update(ctx, pr_id, title, description, description_file, dest,
              add_reviewers, remove_reviewers):
    """Update a pull request's title, description, destination or reviewers.

    \b
    Examples:
      trinity bb -r my-repo update 42 --title "Better title"
      trinity bb -r my-repo update 42 --reviewer dzana --remove-reviewer joshua
    """
    from .bitbucket.api import BitbucketAPI
    from .bitbucket.commands import update_pr
    if description_file:
        with open(description_file) as f:
            description = f.read()
    api = BitbucketAPI()
    workspace, repo = _bb_context(ctx)
    result = update_pr(api, workspace, repo, pr_id,
                       title=title, description=description, dest=dest,
                       add_reviewers=list(add_reviewers),
                       remove_reviewers=list(remove_reviewers))
    if ctx.obj.get("output_json"):
        click.echo(json.dumps(result, indent=2))
    else:
        console.print(f"[green]PR #{pr_id} updated[/green]")
        if add_reviewers or remove_reviewers:
            _print_reviewers(result.get("reviewers") or [])


def _print_reviewers(reviewers) -> None:
    names = [r.get("display_name") or r.get("nickname") or r.get("uuid") for r in reviewers]
    console.print(f"Reviewers: {', '.join(names) if names else '(none)'}")


@bb_group.command("ready")
@click.argument("pr_id", type=int)
@click.option("--client-visible", is_flag=True,
              help="Also add bitbucket.pm_reviewers (for changes clients will see)")
@click.option("--simple", is_flag=True,
              help="Trivial change: skip the CTO tier (bitbucket.cto_reviewers)")
@click.option("--reviewer", "reviewers", multiple=True,
              help="Extra reviewer (UUID {...}, nickname, or alias). Repeatable.")
@click.option("--no-default-reviewers", is_flag=True,
              help="Don't add bitbucket.default_reviewers or bitbucket.cto_reviewers")
@click.pass_context
def bb_ready(ctx, pr_id, client_visible, simple, reviewers, no_default_reviewers):
    """Take a PR out of draft and add the team's reviewers.

    One PUT sets draft to false and adds bitbucket.default_reviewers plus
    bitbucket.cto_reviewers (the CTO tier, almost always), plus
    bitbucket.pm_reviewers with --client-visible, plus any --reviewer. Pass
    --simple for a trivial change to skip the CTO tier. Existing reviewers
    stay, the PR author is skipped, and the title and description are left as
    they are. Safe to run twice: the second run changes nothing.

    \b
    Examples:
      trinity bb -r my-repo ready 42
      trinity bb -r my-repo ready 42 --client-visible
      trinity bb -r my-repo ready 42 --simple
      trinity bb -r my-repo ready 42 --no-default-reviewers --reviewer mohamed
    """
    from .bitbucket.api import BitbucketAPI
    from .bitbucket.commands import ready_pr
    api = BitbucketAPI()
    workspace, repo = _bb_context(ctx)
    result = ready_pr(api, workspace, repo, pr_id,
                      client_visible=client_visible, simple=simple,
                      reviewers=list(reviewers),
                      use_defaults=not no_default_reviewers)
    if ctx.obj.get("output_json"):
        click.echo(json.dumps(result, indent=2))
        return
    state = "draft" if result["draft"] else "ready for review"
    verb = "is now" if result["changed"] else "was already"
    console.print(f"[green]PR #{result['id']} {verb} {state}[/green] ({result['state']}) {result.get('url') or ''}")
    _print_reviewers(result["reviewers"])
    if result["added"]:
        console.print(f"Added {len(result['added'])} reviewer(s).")
    if result["skipped_author"]:
        console.print("[yellow]Skipped the PR author (Bitbucket won't accept them as a reviewer).[/yellow]")


@bb_group.command("run-pipeline")
@click.argument("pattern")
@click.option("-b", "--branch", required=True, help="Branch to run the pipeline on")
@click.pass_context
def bb_run_pipeline(ctx, pattern, branch):
    """Trigger a custom pipeline (e.g. review-app, full-tests) on a branch.

    PATTERN is the custom pipeline name from bitbucket-pipelines.yml's `custom:`
    section, or "default" to run the branch's default pipeline.
    """
    from .bitbucket.api import BitbucketAPI
    api = BitbucketAPI()
    workspace, repo = _bb_context(ctx)
    result = api.trigger_pipeline(
        workspace, repo, branch, pattern=None if pattern == "default" else pattern
    )
    build = result.get("build_number")
    url = f"https://bitbucket.org/{workspace}/{repo}/pipelines/results/{build}"
    if ctx.obj.get("output_json"):
        click.echo(json.dumps({"build_number": build, "uuid": result.get("uuid"),
                               "pattern": pattern, "branch": branch, "url": url}, indent=2))
    else:
        console.print(f"[green]Pipeline #{build} triggered[/green] ({pattern} on {branch}) {url}")


@bb_group.command("pipelines")
@click.argument("pr_id", type=int)
@click.pass_context
def bb_pipelines(ctx, pr_id):
    """Show pipeline status for a pull request.

    \b
    Examples:
      trinity bb -r my-repo pipelines 42
    """
    from .bitbucket.api import BitbucketAPI
    from .bitbucket.commands import get_pipeline_status
    api = BitbucketAPI()
    workspace, repo = _bb_context(ctx)
    result = get_pipeline_status(api, workspace, repo, pr_id=pr_id)
    click.echo(json.dumps(result, indent=2))


# ── Confluence subgroup ────────────────────────────────────────────────────────

@cli.group("confluence", cls=AtlassianGroup)
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
    """Search Confluence pages.

    \b
    Examples:
      trinity confluence search "release process" --space ENG
    """
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
    """Get a Confluence page by ID.

    \b
    Examples:
      trinity confluence get 123456
    """
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


@confluence_group.command("attach")
@click.argument("page_id")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def confluence_attach(ctx, page_id, files):
    """Attach files (e.g. screenshots) to a Confluence page.

    Prints, per file, the storage-format markup that embeds it in the page body.
    Re-attaching the same filename adds a new version.
    """
    from .confluence.attach_files import attach_confluence_files
    result = attach_confluence_files(page_id, list(files))
    click.echo(json.dumps(result, indent=2))
    if result.get("error"):
        sys.exit(1)


# ── Config command ─────────────────────────────────────────────────────────────

@cli.command("config")
@click.option("--email", help="Atlassian account email")
@click.option("--token", help="Atlassian API token")
@click.option("--cloud-id", help="Atlassian Cloud ID")
@click.option("--jira-url", help="Jira instance URL (e.g., https://co.atlassian.net)")
@click.option("--bb-token", help="Bitbucket workspace-level repo access token (Bearer)")
@click.option(
    "--bb-repo-token",
    "bb_repo_tokens",
    multiple=True,
    help="Per-repo Bitbucket token in WORKSPACE/REPO=TOKEN form. Repeatable. "
         "Slug matches the auto-extracted /repositories/{workspace}/{repo}/... "
         "path used by the API client, so a workspace prefix is required. "
         "Takes precedence over --bb-token for matching repos. "
         "Example: --bb-repo-token citemed/ai_backend=ATCTT... "
         "--bb-repo-token citemed/citemed_web=ATCTT...",
)
@click.option(
    "--bb-repo-token-remove",
    "bb_repo_tokens_remove",
    multiple=True,
    help="Remove a per-repo Bitbucket token by WORKSPACE/REPO slug. Repeatable.",
)
@click.option("--bb-workspace", help="Default Bitbucket workspace")
@click.option("--bb-default-reviewer", "bb_default_reviewers", multiple=True,
              help="Add to bitbucket.default_reviewers (used by `bb ready`): UUID, nickname or alias. Repeatable.")
@click.option("--bb-default-reviewer-remove", "bb_default_reviewers_remove", multiple=True,
              help="Remove from bitbucket.default_reviewers. Repeatable.")
@click.option("--bb-pm-reviewer", "bb_pm_reviewers", multiple=True,
              help="Add to bitbucket.pm_reviewers (added by `bb ready --client-visible`). Repeatable.")
@click.option("--bb-pm-reviewer-remove", "bb_pm_reviewers_remove", multiple=True,
              help="Remove from bitbucket.pm_reviewers. Repeatable.")
@click.option("--bb-cto-reviewer", "bb_cto_reviewers", multiple=True,
              help="Add to bitbucket.cto_reviewers (added by `bb ready` unless --simple). Repeatable.")
@click.option("--bb-cto-reviewer-remove", "bb_cto_reviewers_remove", multiple=True,
              help="Remove from bitbucket.cto_reviewers. Repeatable.")
@click.option("--bb-reviewer-alias", "bb_reviewer_aliases", multiple=True,
              help="Reviewer alias in NAME={UUID} form, e.g. devbot={55a6...}. Repeatable.")
@click.option("--bb-reviewer-alias-remove", "bb_reviewer_aliases_remove", multiple=True,
              help="Remove a reviewer alias by name. Repeatable.")
@click.option("--list", "list_config", is_flag=True, help="Show current config")
@click.option("--reset", is_flag=True, help="Reset to defaults")
def config(email, token, cloud_id, jira_url, bb_token, bb_repo_tokens,
           bb_repo_tokens_remove, bb_workspace, bb_default_reviewers,
           bb_default_reviewers_remove, bb_pm_reviewers, bb_pm_reviewers_remove,
           bb_cto_reviewers, bb_cto_reviewers_remove,
           bb_reviewer_aliases, bb_reviewer_aliases_remove, list_config, reset):
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
        # Mask tokens (top-level + per-repo)
        if display.get("atlassian", {}).get("api_token"):
            display["atlassian"]["api_token"] = "***"
        if display.get("bitbucket", {}).get("repo_token"):
            display["bitbucket"]["repo_token"] = "***"
        repo_tokens = display.get("bitbucket", {}).get("repo_tokens") or {}
        if repo_tokens:
            display["bitbucket"]["repo_tokens"] = {k: "***" for k in repo_tokens}
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

    repo_tokens_changed = False
    if bb_repo_tokens or bb_repo_tokens_remove:
        cfg["bitbucket"].setdefault("repo_tokens", {})
        for pair in bb_repo_tokens:
            if "=" not in pair:
                raise click.UsageError(
                    f"--bb-repo-token expects REPO=TOKEN, got: {pair!r}"
                )
            repo_slug, repo_token_value = pair.split("=", 1)
            repo_slug = repo_slug.strip()
            repo_token_value = repo_token_value.strip()
            if not repo_slug or not repo_token_value:
                raise click.UsageError(
                    f"--bb-repo-token needs a non-empty repo and token: {pair!r}"
                )
            cfg["bitbucket"]["repo_tokens"][repo_slug] = repo_token_value
            repo_tokens_changed = True
        for repo_slug in bb_repo_tokens_remove:
            cfg["bitbucket"]["repo_tokens"].pop(repo_slug.strip(), None)
            repo_tokens_changed = True

    reviewers_changed = _apply_reviewer_config(
        cfg["bitbucket"], bb_default_reviewers, bb_default_reviewers_remove,
        bb_pm_reviewers, bb_pm_reviewers_remove,
        bb_cto_reviewers, bb_cto_reviewers_remove,
        bb_reviewer_aliases, bb_reviewer_aliases_remove,
    )

    if any([email, token, cloud_id, jira_url, bb_token, bb_workspace,
            repo_tokens_changed, reviewers_changed]):
        save_config(cfg)
        if repo_tokens_changed:
            slugs = sorted((cfg["bitbucket"].get("repo_tokens") or {}).keys())
            console.print(
                f"[green]Config saved.[/green] Per-repo tokens now set for: "
                f"{', '.join(slugs) if slugs else '(none)'}"
            )
        else:
            console.print("[green]Config saved.[/green]")
    else:
        console.print("Use options to set values. Run [cyan]trinity config --help[/cyan] for details.")


def _apply_reviewer_config(bb, add_default, rm_default, add_pm, rm_pm,
                           add_cto, rm_cto, add_alias, rm_alias) -> bool:
    """Edit the reviewer lists and aliases in the bitbucket config section."""
    changed = False
    for key, adds, removes in (("default_reviewers", add_default, rm_default),
                               ("pm_reviewers", add_pm, rm_pm),
                               ("cto_reviewers", add_cto, rm_cto)):
        if not (adds or removes):
            continue
        values = list(bb.get(key) or [])
        for v in adds:
            v = v.strip()
            if v and v not in values:
                values.append(v)
        drop = {v.strip() for v in removes}
        bb[key] = [v for v in values if v not in drop]
        changed = True
    if add_alias or rm_alias:
        aliases = dict(bb.get("reviewer_aliases") or {})
        for pair in add_alias:
            if "=" not in pair:
                raise click.UsageError(f"--bb-reviewer-alias expects NAME={{UUID}}, got: {pair!r}")
            name, target = (x.strip() for x in pair.split("=", 1))
            if not name or not target:
                raise click.UsageError(f"--bb-reviewer-alias needs a name and a target: {pair!r}")
            aliases[name.lower()] = target
        for name in rm_alias:
            aliases.pop(name.strip().lower(), None)
        bb["reviewer_aliases"] = aliases
        changed = True
    return changed


# ── Doctor ─────────────────────────────────────────────────────────────────────

@cli.command("doctor")
@click.pass_context
def doctor(ctx):
    """Check that every login and repo token actually works.

    Run this first when a command fails or returns less than you expected.
    Exits non-zero if any check fails.

    \b
    Examples:
      trinity doctor
      trinity doctor --table
    """
    from .base.health import run_checks
    report = run_checks()

    if ctx.obj.get("output_json"):
        click.echo(json.dumps(report, indent=2))
    else:
        table = Table(title=f"Trinity doctor ({report['config_file']})")
        table.add_column("Check", style="cyan")
        table.add_column("OK")
        table.add_column("Detail")
        for c in report["checks"]:
            table.add_row(c["check"], "[green]yes[/green]" if c["ok"] else "[red]NO[/red]", c["detail"])
        console.print(table)

    if not report["ok"]:
        sys.exit(1)


def _report_error(error: Exception) -> None:
    explicit = True if "--json" in sys.argv else False if "--table" in sys.argv else None
    if _wants_json(explicit):
        click.echo(json.dumps({"error": True, "error_type": type(error).__name__,
                               "message": str(error)}, indent=2))
    else:
        click.echo(f"Error: {error}", err=True)


def main():
    """CLI entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        sys.exit(1)
    except TrinityError as e:
        # These carry a remediation hint in their message. Letting them
        # escape printed a ~20-line traceback that buried it.
        _report_error(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
