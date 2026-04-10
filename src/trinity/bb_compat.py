#!/usr/bin/env python3
"""``bb`` — gh-style Bitbucket CLI entry point.

Provides the same command surface as the retired ``bitbucket-cli-for-claude-code``
project while delegating all real work to Trinity's Bitbucket API layer.

Command groups:
  bb pr      — pull request operations
  bb run     — pipeline (build) operations
  bb auth    — authentication / config
"""

import functools
import json
import os
import re
import sys
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .base.auth import (
    get_bitbucket_auth_headers,
    is_authenticated as _is_authenticated,
    load_config,
    save_config,
)
from .base.exceptions import AuthenticationError
from .bitbucket.api import BitbucketAPI
from .bitbucket.commands import (
    approve_pr,
    comment_pr,
    create_pr,
    decline_pr,
    get_pipeline_status,
    list_prs,
    merge_pr,
    show_pr,
    unapprove_pr,
)

console = Console()


# ─── Helpers ──────────────────────────────────────────────────────────


def _success(msg: str) -> None:
    console.print(f"[bold green]{msg}[/bold green]")


def _error(msg: str) -> None:
    console.print(f"[bold red]{msg}[/bold red]")


def _api() -> BitbucketAPI:
    return BitbucketAPI()


def _resolve_repo(ctx):
    """Resolve workspace/repo from flags, env, or current git remote."""
    workspace = ctx.obj.get("workspace")
    repo = ctx.obj.get("repo")
    if not workspace or not repo:
        try:
            from git import Repo, InvalidGitRepositoryError
            git_repo = Repo(search_parent_directories=True)
            for remote in git_repo.remotes:
                m = re.search(r"bitbucket\.org[:/]([^/]+)/([^/.]+)", remote.url)
                if m:
                    workspace = workspace or m.group(1)
                    repo = repo or m.group(2)
                    break
        except Exception:
            pass
    return workspace or "", repo or ""


def _get_current_branch() -> str:
    """Return the current git branch name."""
    try:
        from git import Repo
        repo = Repo(search_parent_directories=True)
        if repo.head.is_detached:
            return repo.head.commit.hexsha[:8]
        return repo.active_branch.name
    except Exception:
        return ""


def validate_auth(f):
    """Decorator that aborts early when Bitbucket credentials are missing."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not _is_authenticated("bitbucket"):
            _error("Authentication not configured. Run: bb auth login")
            sys.exit(1)
        return f(*args, **kwargs)
    return wrapper


# ─── Top-level group ──────────────────────────────────────────────────


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="trinity-atlassian-cli")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.option("--no-color", is_flag=True, help="Disable colored output")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
@click.option("-w", "--workspace", help="Override default workspace")
@click.option("-R", "--repo", help="Override repo (name only or workspace/name)")
@click.pass_context
def cli(ctx, verbose, no_color, output_json, workspace, repo):
    """Bitbucket Cloud CLI — gh-style commands for Bitbucket repos.

    Run ``bb <group> --help`` for group-specific commands:

    \b
      bb pr --help      pull request operations
      bb run --help     pipeline (build) operations
      bb auth --help    authentication
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["no_color"] = no_color
    ctx.obj["output_json"] = output_json

    # Allow ``--repo workspace/name`` shorthand like gh
    if repo and "/" in repo:
        ws_from_repo, _, repo_name = repo.partition("/")
        ctx.obj["workspace"] = workspace or ws_from_repo
        ctx.obj["repo"] = repo_name
    else:
        ctx.obj["workspace"] = workspace
        ctx.obj["repo"] = repo


# ─── ``bb pr`` group ──────────────────────────────────────────────────


@cli.group()
def pr():
    """Manage pull requests (gh-style: ``bb pr create``, ``bb pr list``, ...)."""


@pr.command("create")
@click.option("-t", "--title", help="PR title")
@click.option("-b", "--body", "description", help="PR body / description")
@click.option("-d", "--description", "description", help="Alias for --body")
@click.option("-s", "--source", help="Source branch (defaults to current)")
@click.option("-B", "--base", "dest", help="Destination/base branch (defaults to main)")
@click.option("--dest", "dest", help="Alias for --base")
@click.option("-r", "--reviewers", help="Comma-separated list of reviewers")
@click.option("--close-branch", is_flag=True, help="Close source branch when merged")
@click.option("--web", is_flag=True, help="Open in web browser after creation")
@click.pass_context
@validate_auth
def pr_create(ctx, title, description, source, dest, reviewers, close_branch, web):
    """Create a pull request."""
    try:
        workspace, repo = _resolve_repo(ctx)
        result = create_pr(
            _api(), workspace, repo,
            title=title, description=description, source=source, dest=dest,
            reviewers=reviewers, close_branch=close_branch, web=web,
        )
        if ctx.obj["output_json"]:
            click.echo(json.dumps(result, indent=2))
        else:
            _success(f"Pull request #{result['id']} created successfully")
            html = result.get("links", {}).get("html", {}).get("href", "")
            if html:
                console.print(f"  {html}")
    except Exception as e:
        _error(f"Failed to create PR: {e}")
        sys.exit(1)


@pr.command("list")
@click.option("--state", default="OPEN", help="Filter by state (OPEN, MERGED, DECLINED, SUPERSEDED)")
@click.option("--author", help="Filter by author username")
@click.option("--reviewer", help="Filter by reviewer username")
@click.option("-L", "--limit", default=25, help="Number of results")
@click.option("--all", "fetch_all", is_flag=True, help="Fetch all pages")
@click.pass_context
@validate_auth
def pr_list(ctx, state, author, reviewer, limit, fetch_all):
    """List pull requests."""
    try:
        workspace, repo = _resolve_repo(ctx)
        prs = list_prs(
            _api(), workspace, repo,
            state=state, author=author, reviewer=reviewer,
            limit=limit, fetch_all=fetch_all,
        )
        if ctx.obj["output_json"]:
            click.echo(json.dumps(prs, indent=2))
            return
        if not prs:
            console.print("No pull requests found.", style="yellow")
            return
        table = Table(title="Pull Requests")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="bold")
        table.add_column("Author", style="green")
        table.add_column("State", style="magenta")
        table.add_column("Created", style="dim")
        for p in prs:
            a = p.get("author", {}) or {}
            author_name = (
                a.get("username") or a.get("nickname")
                or a.get("display_name") or "Unknown"
            )
            title_text = p["title"][:50] + "..." if len(p["title"]) > 50 else p["title"]
            table.add_row(
                str(p["id"]), title_text, author_name,
                p["state"], (p.get("created_on") or "")[:10],
            )
        console.print(table)
    except Exception as e:
        _error(f"Failed to list PRs: {e}")
        sys.exit(1)


@pr.command("view")
@click.argument("pr_id", type=int)
@click.option("--web", is_flag=True, help="Open PR in web browser")
@click.option("-c", "--comments", is_flag=True, help="Include comments in output")
@click.pass_context
@validate_auth
def pr_view(ctx, pr_id, web, comments):
    """View a pull request."""
    try:
        workspace, repo = _resolve_repo(ctx)
        pr_data = show_pr(_api(), workspace, repo, pr_id, web=web, include_comments=comments)
        if ctx.obj["output_json"]:
            click.echo(json.dumps(pr_data, indent=2, default=str))
        else:
            _format_pr_detail(pr_data)
    except Exception as e:
        _error(f"Failed to view PR: {e}")
        sys.exit(1)


@pr.command("review")
@click.argument("pr_id", type=int)
@click.option("--approve", "action", flag_value="approve", help="Approve the PR")
@click.option("--unapprove", "action", flag_value="unapprove", help="Remove your approval")
@click.option(
    "--request-changes", "action", flag_value="request_changes",
    help="Request changes (posts a comment with REQUEST_CHANGES marker)",
)
@click.option("-b", "--body", help="Comment body (used with --request-changes)")
@click.pass_context
@validate_auth
def pr_review(ctx, pr_id, action, body):
    """Approve, unapprove, or request changes on a pull request.

    gh-style: ``bb pr review 123 --approve``
    """
    if not action:
        _error("Specify one of: --approve, --unapprove, --request-changes")
        sys.exit(2)
    try:
        workspace, repo = _resolve_repo(ctx)
        api = _api()
        if action == "approve":
            result = approve_pr(api, workspace, repo, pr_id)
            _success(f"PR #{pr_id} approved")
        elif action == "unapprove":
            result = unapprove_pr(api, workspace, repo, pr_id)
            _success(f"Approval removed from PR #{pr_id}")
        else:
            text = body or "Requesting changes."
            result = comment_pr(api, workspace, repo, pr_id, message=f"[REQUEST_CHANGES] {text}")
            _success(f"Posted change-request comment on PR #{pr_id}")
        if ctx.obj["output_json"]:
            click.echo(json.dumps(result, indent=2))
    except Exception as e:
        _error(f"Failed to review PR: {e}")
        sys.exit(1)


@pr.command("close")
@click.argument("pr_id", type=int)
@click.option("-m", "--message", help="Decline message")
@click.pass_context
@validate_auth
def pr_close(ctx, pr_id, message):
    """Close (decline) a pull request without merging."""
    try:
        workspace, repo = _resolve_repo(ctx)
        result = decline_pr(_api(), workspace, repo, pr_id, message=message)
        _success(f"PR #{pr_id} closed")
        if ctx.obj["output_json"]:
            click.echo(json.dumps(result, indent=2))
    except Exception as e:
        _error(f"Failed to close PR: {e}")
        sys.exit(1)


@pr.command("merge")
@click.argument("pr_id", type=int)
@click.option("-m", "--message", help="Merge commit message")
@click.option(
    "-s", "--strategy",
    type=click.Choice(["merge_commit", "squash", "fast_forward"]),
    default="merge_commit", show_default=True, help="Merge strategy",
)
@click.option("-d", "--delete-branch", "close_branch", is_flag=True,
              help="Delete source branch after merge")
@click.pass_context
@validate_auth
def pr_merge(ctx, pr_id, message, strategy, close_branch):
    """Merge a pull request."""
    try:
        workspace, repo = _resolve_repo(ctx)
        result = merge_pr(
            _api(), workspace, repo, pr_id,
            message=message, strategy=strategy, close_branch=close_branch,
        )
        _success(f"PR #{pr_id} merged")
        if ctx.obj["output_json"]:
            click.echo(json.dumps(result, indent=2))
    except Exception as e:
        _error(f"Failed to merge PR: {e}")
        sys.exit(1)


@pr.command("comment")
@click.argument("pr_id", type=int)
@click.option("-b", "--body", "message", help="Comment body")
@click.option("-m", "--message", "message", help="Alias for --body")
@click.option("--file", help="File path for inline comment")
@click.option("--line", type=int, help="Line number for inline comment")
@click.option("--from-line", type=int, help="Starting line for multi-line comment")
@click.option("--to-line", type=int, help="Ending line for multi-line comment")
@click.option("--reply-to", type=int, help="Reply to existing comment ID")
@click.pass_context
@validate_auth
def pr_comment(ctx, pr_id, message, file, line, from_line, to_line, reply_to):
    """Add a comment to a pull request."""
    try:
        workspace, repo = _resolve_repo(ctx)
        if not message:
            message = click.prompt("Comment")
        result = comment_pr(
            _api(), workspace, repo, pr_id,
            message=message, file=file, line=line,
            from_line=from_line, to_line=to_line, reply_to=reply_to,
        )
        _success(f"Comment added to PR #{pr_id}")
        if ctx.obj["output_json"]:
            click.echo(json.dumps(result, indent=2))
    except Exception as e:
        _error(f"Failed to add comment: {e}")
        sys.exit(1)


# ─── ``bb run`` group (pipelines) ────────────────────────────────────


@cli.group()
def run():
    """Manage pipeline runs (``gh run`` equivalent)."""


@run.command("list")
@click.option("-b", "--branch", help="Filter by branch name")
@click.option("--pr", "pr_id", type=int, help="Filter by PR ID (uses PR's source branch)")
@click.option("-L", "--limit", default=5, show_default=True, help="Number of pipelines to show")
@click.option("-l", "--logs", is_flag=True, help="Show failure log tails for failed steps")
@click.pass_context
@validate_auth
def run_list(ctx, branch, pr_id, limit, logs):
    """List recent pipeline runs."""
    try:
        workspace, repo = _resolve_repo(ctx)

        if not branch and not pr_id:
            branch = _get_current_branch()

        pipelines = get_pipeline_status(
            _api(), workspace, repo,
            branch=branch, pr_id=pr_id, limit=limit,
        )

        if ctx.obj["output_json"]:
            click.echo(json.dumps(pipelines, indent=2))
            return

        if not pipelines:
            console.print("No pipelines found.", style="yellow")
            return

        result_styles = {
            "SUCCESSFUL": "green", "FAILED": "red",
            "STOPPED": "yellow", "ERROR": "red",
        }
        state_styles = {"IN_PROGRESS": "yellow", "PENDING": "yellow", "COMPLETED": "dim"}

        def _rs(result, state):
            return result_styles.get(result, state_styles.get(state, "white"))

        table = Table(title="Pipelines")
        table.add_column("#", style="cyan")
        table.add_column("Branch", style="bold")
        table.add_column("State", style="dim")
        table.add_column("Result")
        table.add_column("Duration", justify="right")
        table.add_column("Created", style="dim")

        for p in pipelines:
            style = _rs(p["result"], p["state"])
            duration = f"{p['duration_in_seconds']}s" if p.get("duration_in_seconds") else "-"
            label = p.get("result") or p.get("state") or "-"
            table.add_row(
                str(p["build_number"]), p.get("branch") or "-",
                p.get("state") or "-", label, duration,
                (p.get("created_on") or "")[:19],
                style=style if p.get("result") in ("FAILED", "SUCCESSFUL") else None,
            )
        console.print(table)

        # Step details
        for p in pipelines:
            if not p.get("steps"):
                continue
            console.print(f"\n[bold]Pipeline #{p['build_number']} steps:[/bold]")
            step_table = Table(show_header=True, header_style="bold")
            step_table.add_column("Step")
            step_table.add_column("Result")
            step_table.add_column("Duration", justify="right")
            for step in p["steps"]:
                ss = _rs(step.get("result"), step.get("state"))
                sd = f"{step['duration_in_seconds']}s" if step.get("duration_in_seconds") else "-"
                step_table.add_row(
                    step.get("name") or "-",
                    step.get("result") or step.get("state") or "-",
                    sd,
                    style=ss if step.get("result") in ("FAILED", "SUCCESSFUL") else None,
                )
            console.print(step_table)

            if logs:
                for step in p["steps"]:
                    if step.get("log_tail"):
                        console.print(Panel(
                            step["log_tail"],
                            title=f"[red]Log tail: {step.get('name')}[/red]",
                            border_style="red",
                        ))
    except Exception as e:
        _error(f"Failed to list pipeline runs: {e}")
        sys.exit(1)


# ─── ``bb auth`` group ───────────────────────────────────────────────


@cli.group()
def auth():
    """Authentication and configuration."""


@auth.command("login")
@click.option("--repo-token", help="Repository access token (recommended)")
@click.option("--username", help="Bitbucket username")
@click.option("--app-password", help="App password")
@click.option("--workspace", help="Default workspace")
def auth_login(repo_token, username, app_password, workspace):
    """Configure Bitbucket credentials.

    Interactive if no flags given.
    """
    try:
        cfg = load_config()

        if any([repo_token, username, app_password, workspace]):
            if repo_token:
                cfg["bitbucket"]["repo_token"] = repo_token
                cfg["bitbucket"]["username"] = None
                cfg["bitbucket"]["app_password"] = None
            if username:
                cfg["bitbucket"]["username"] = username
            if app_password:
                cfg["bitbucket"]["app_password"] = app_password
            if workspace:
                cfg["bitbucket"]["workspace"] = workspace
            save_config(cfg)
            _success("Configuration updated successfully")
            return

        click.echo("Choose authentication method:")
        click.echo("1. Repository access token (recommended)")
        click.echo("2. Username + app password")
        choice = click.prompt("Choice", type=click.Choice(["1", "2"]), default="1")

        if choice == "1":
            token = click.prompt("Repository access token", hide_input=True)
            ws = click.prompt(
                "Workspace",
                default=cfg.get("bitbucket", {}).get("workspace") or "",
            )
            cfg["bitbucket"]["repo_token"] = token
            cfg["bitbucket"]["username"] = None
            cfg["bitbucket"]["app_password"] = None
            if ws:
                cfg["bitbucket"]["workspace"] = ws
        else:
            user = click.prompt(
                "Username",
                default=cfg.get("bitbucket", {}).get("username") or "",
            )
            pw = click.prompt("App Password", hide_input=True)
            ws = click.prompt(
                "Workspace",
                default=cfg.get("bitbucket", {}).get("workspace") or "",
            )
            cfg["bitbucket"]["username"] = user
            cfg["bitbucket"]["app_password"] = pw
            if ws:
                cfg["bitbucket"]["workspace"] = ws

        save_config(cfg)
        _success("Configuration saved successfully")
    except Exception as e:
        _error(f"Login failed: {e}")
        sys.exit(1)


@auth.command("status")
def auth_status():
    """Show current authentication status."""
    try:
        cfg = load_config()
        display = json.loads(json.dumps(cfg))
        # Mask secrets
        bb = display.get("bitbucket", {})
        for key in ("repo_token", "app_password"):
            if bb.get(key):
                bb[key] = "***hidden***"
        atl = display.get("atlassian", {})
        if atl.get("api_token"):
            atl["api_token"] = "***hidden***"

        click.echo(json.dumps(display, indent=2))
        if _is_authenticated("bitbucket"):
            _success("Authenticated (Bitbucket)")
        else:
            _error("Not authenticated -- run `bb auth login`")
            sys.exit(1)
    except Exception as e:
        _error(f"Failed to read auth status: {e}")
        sys.exit(1)


@auth.command("logout")
def auth_logout():
    """Reset stored Bitbucket credentials."""
    try:
        cfg = load_config()
        cfg["bitbucket"] = {
            "repo_token": None,
            "username": None,
            "app_password": None,
            "workspace": None,
        }
        save_config(cfg)
        _success("Bitbucket credentials cleared")
    except Exception as e:
        _error(f"Failed to reset config: {e}")
        sys.exit(1)


# ─── Pretty-print helpers ────────────────────────────────────────────


def _format_pr_detail(pr_data: dict) -> None:
    """Rich-format a single PR for terminal display."""
    title_line = f"#{pr_data['id']}  {pr_data['title']}"
    console.print(Panel(title_line, subtitle=f"State: {pr_data['state']}", border_style="blue"))

    rows = []
    author = pr_data.get("author", {}) or {}
    rows.append(("Author", author.get("display_name") or author.get("username") or "Unknown"))

    src = pr_data.get("source", {}).get("branch", {}).get("name")
    dst = pr_data.get("destination", {}).get("branch", {}).get("name")
    if src:
        rows.append(("Source", src))
    if dst:
        rows.append(("Destination", dst))

    if pr_data.get("created_on"):
        rows.append(("Created", pr_data["created_on"][:19].replace("T", " ")))

    reviewers = pr_data.get("reviewers", [])
    if reviewers:
        names = [r.get("display_name") or r.get("username") or "?" for r in reviewers]
        rows.append(("Reviewers", ", ".join(names)))

    html = pr_data.get("links", {}).get("html", {}).get("href")
    if html:
        rows.append(("URL", html))

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Field", style="bold cyan", min_width=15)
    table.add_column("Value")
    for k, v in rows:
        table.add_row(k, v)
    console.print(table)

    desc = (pr_data.get("description") or "").strip()
    if desc:
        console.print("\n[bold cyan]Description:[/bold cyan]")
        console.print(Panel(desc, border_style="dim"))


# ─── Entry point ──────────────────────────────────────────────────────


def main():
    """CLI entry point registered as the ``bb`` console script."""
    try:
        cli()
    except KeyboardInterrupt:
        _error("Operation cancelled")
        sys.exit(1)


if __name__ == "__main__":
    main()
