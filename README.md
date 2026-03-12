# Trinity

**Unified Atlassian CLI for Jira, Confluence, and Bitbucket.**

Trinity is a pip-installable command-line tool that wraps the Jira, Confluence, and Bitbucket Cloud REST APIs into a single, consistent interface. It runs in human-readable Rich terminal output by default and switches to clean, structured JSON with `--json` — making it equally at home in a developer's terminal or an agent's subprocess call.

Sister project to [Morpheus](https://github.com/ethandrower/morpheus), an autonomous project management agent.

---

## Installation

```bash
git clone https://github.com/ethandrower/trinity-atlassian-cli
cd trinity-atlassian-cli
pip install -e .
```

For an isolated environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires Python 3.9+.

---

## Configuration

Trinity resolves credentials in priority order: environment variables first, then `~/.trinity/config.yaml`.

### Environment Variables

```bash
# Jira + Confluence (same Atlassian account)
ATLASSIAN_EMAIL=you@yourcompany.com
ATLASSIAN_API_TOKEN=your-api-token
ATLASSIAN_CLOUD_ID=your-cloud-id
ATLASSIAN_JIRA_URL=https://yourinstance.atlassian.net

# Service account fallback (used if primary vars are not set)
ATLASSIAN_SERVICE_ACCOUNT_EMAIL=bot@yourcompany.com
ATLASSIAN_SERVICE_ACCOUNT_TOKEN=bot-api-token

# Bitbucket
BITBUCKET_REPO_TOKEN=your-repo-access-token
BITBUCKET_WORKSPACE=your-workspace

# Bitbucket Basic Auth fallback
BITBUCKET_USERNAME=your-username
BITBUCKET_APP_PASSWORD=your-app-password
```

Put these in a `.env` file in your project directory — Trinity loads it automatically via `python-dotenv`.

### Config File

Persist credentials to `~/.trinity/config.yaml` (file is created with 600 permissions):

```bash
trinity config --email you@co.com --token YOUR_TOKEN
trinity config --cloud-id YOUR_CLOUD_ID --jira-url https://yourco.atlassian.net
trinity config --bb-token YOUR_BB_TOKEN --bb-workspace yourworkspace

# View current config (tokens masked)
trinity config --list

# Reset to defaults
trinity config --reset
```

---

## Quick Start

```bash
# Search for in-progress tickets
trinity jira search "project = PROJ AND status = 'In Progress'"

# Show a specific issue with comments
trinity jira show PROJ-123 --comments

# Transition a ticket
trinity jira transition PROJ-123 "In Review"

# List open PRs (auto-detects workspace/repo from git remote)
trinity bb list

# Get a Confluence page
trinity confluence get 123456789

# Search Confluence
trinity confluence search "deployment runbook"
```

---

## Global Flags

These flags must appear **before** the subcommand:

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable JSON output. Must precede the subcommand: `trinity --json jira search "..."` |
| `--no-color` | Disable Rich terminal colors |
| `--version` | Show version and exit |

---

## Jira Commands

Full reference: [docs/jira.md](docs/jira.md)

```
trinity jira <command> [options]
```

### `search <jql>`

Search issues using JQL.

```bash
trinity jira search "project = ECD AND status = 'In Progress'"
trinity jira search "assignee = currentUser() AND sprint in openSprints()" --max-results 20
```

Options: `--max-results INT` (default 50), `--fields TEXT` (comma-separated field list)

Human output:
```
┌──────────┬─────────────────────────────┬─────────────┬──────────────────┬──────────┐
│ Key      │ Summary                     │ Status      │ Assignee         │ Priority │
├──────────┼─────────────────────────────┼─────────────┼──────────────────┼──────────┤
│ ECD-1448 │ Redesign Abstract Screening │ In Progress │ Mohamed Belkahla │ Highest  │
│ ECD-1392 │ Fix search ranking bug      │ In Progress │ Sarah Chen       │ High     │
└──────────┴─────────────────────────────┴─────────────┴──────────────────┴──────────┘
```

JSON output (`trinity --json jira search "..." --max-results 2`):
```json
{
  "total": 42,
  "count": 2,
  "issues": [
    {
      "key": "ECD-1448",
      "summary": "Redesign Abstract Screening",
      "status": "In Progress",
      "assignee": "Mohamed Belkahla",
      "assignee_id": "557058:abc123",
      "priority": "Highest",
      "type": "Story",
      "labels": ["frontend"],
      "created": "2026-02-10T09:00:00.000+0000",
      "updated": "2026-03-10T14:23:00.000+0000"
    }
  ]
}
```

### `show <issue-key>`

Get full issue details including description, assignee, sprint, and optionally comments.

```bash
trinity jira show ECD-1448
trinity jira show ECD-1448 --comments
```

Options: `--comments` (include last 20 comments)

### `comment <issue-key> <text>`

Add an ADF comment to an issue. Supports @-mentions by account ID.

```bash
trinity jira comment ECD-1448 "PR is merged, moving to QA."
trinity jira comment ECD-1448 "Hey @John, can you review?" \
  --mention 557058:abc123 "John Smith"
```

Options: `--mention ACCOUNT_ID NAME` (repeatable)

### `transition <issue-key> <transition-name>`

Move an issue to a new status. Use a name (case-insensitive partial match) or `--id`.

```bash
trinity jira transition ECD-1448 "In Review"
trinity jira transition ECD-1448 --id 31
trinity jira transition ECD-1448 "Done" --comment "All review comments addressed."
```

Options: `--id TEXT`, `--comment TEXT`

### `transitions <issue-key>`

List available status transitions for an issue.

```bash
trinity jira transitions ECD-1448
```

### `edit <issue-key>`

Update issue fields. Assignee must be a Jira account ID (use `trinity jira user` to look up).

```bash
trinity jira edit ECD-1448 --priority High
trinity jira edit ECD-1448 --summary "Updated title"
trinity jira edit ECD-1448 --assignee 557058:abc123
trinity jira edit ECD-1448 --labels "backend,api"
trinity jira edit ECD-1448 --add-labels "urgent" --remove-labels "draft"
```

Options: `--summary TEXT`, `--priority TEXT`, `--assignee ACCOUNT_ID`, `--labels TEXT` (replaces all), `--add-labels TEXT`, `--remove-labels TEXT`

### `status-history <issue-key>`

Time-in-status analysis. Shows how long the issue has been in its current status, with optional full transition history.

```bash
trinity jira status-history ECD-1448
trinity jira status-history ECD-1448 --target-status "In Review"
trinity jira status-history ECD-1448 --all-transitions
```

Options: `--target-status TEXT`, `--all-transitions`

### `user <query>`

Look up a Jira user by name or email. Returns account ID for use in `edit --assignee` and `comment --mention`.

```bash
trinity jira user "john smith"
trinity jira user "sarah@company.com"
```

Options: `--max-results INT` (default 10)

### `projects`

List all visible Jira projects.

```bash
trinity jira projects
trinity jira projects --search "eng"
```

Options: `--search TEXT`

### `boards`

List Jira Agile boards.

```bash
trinity jira boards
trinity jira boards --project ECD --type scrum
```

Options: `--project TEXT`, `--type scrum|kanban`

> **Note:** Boards and sprints use the Jira Agile API, which requires a personal API token. Service accounts may lack the required scope.

### `sprints <board-id>`

List sprints for a board.

```bash
trinity jira sprints 42
trinity jira sprints 42 --state active
trinity jira sprints 42 --active
```

Options: `--state active|closed|future`, `--active` (returns single active sprint object)

### `sprint-issues <sprint-id>`

Get issues in a sprint.

```bash
trinity jira sprint-issues 188
trinity jira sprint-issues 188 --status "In Progress"
trinity jira sprint-issues 188 --completed-only
```

Options: `--status TEXT`, `--completed-only`, `--max-results INT` (default 100)

### `worklogs <issue-key>`

Get time-tracking worklogs for an issue.

```bash
trinity jira worklogs ECD-1448
trinity jira worklogs ECD-1448 --days 7
```

Options: `--days INT` (filter to last N days)

### `release-issues`

Get completed issues for release notes, grouped by issue type.

```bash
trinity jira release-issues --project ECD --days 14
trinity jira release-issues --fix-version "v2.1.0"
trinity jira release-issues --current-sprint
```

Options: `--project TEXT`, `--days INT` (default 14), `--fix-version TEXT`, `--current-sprint`

---

## Bitbucket Commands

Full reference: [docs/bitbucket.md](docs/bitbucket.md)

```
trinity bb [--workspace WS] [--repo REPO] <command> [options]
```

`--workspace` and `--repo` can be omitted when running from inside a git repo with a Bitbucket remote — Trinity detects them from the remote URL automatically. Set `BITBUCKET_WORKSPACE` in your environment to avoid passing `--workspace` every time.

### `list`

List pull requests.

```bash
trinity bb --workspace myco --repo backend list
trinity bb list --state MERGED --limit 10
```

Options: `--state OPEN|MERGED|DECLINED` (default OPEN), `--author TEXT`, `--limit INT` (default 25), `--all` (fetch all pages)

### `show <pr-id>`

Show full PR details.

```bash
trinity bb show 47
trinity bb show 47 --comments
```

Options: `--comments` (include all PR comments)

### `create`

Create a pull request. Source branch defaults to current git branch.

```bash
trinity bb create --title "Add search ranking improvements" \
  --source feature/search-ranking --destination main \
  --reviewers alice,bob
```

Options: `--title TEXT`, `--description TEXT`, `--source TEXT`, `--destination TEXT` (default main), `--reviewers TEXT` (comma-separated usernames)

### `comment <pr-id>`

Add a comment to a PR. Supports inline comments on specific files and lines.

```bash
trinity bb comment 47 --message "LGTM, approved."
trinity bb comment 47 --message "Consider extracting this function" \
  --file src/search.py --line 42
trinity bb comment 47 --message "Agreed" --reply-to 891
```

Options: `--message/-m TEXT` (required), `--file TEXT`, `--line INT`, `--reply-to INT`

### `approve <pr-id>`

Approve a pull request.

```bash
trinity bb approve 47
```

### `decline <pr-id>`

Decline a pull request.

```bash
trinity bb decline 47
```

### `merge <pr-id>`

Merge a pull request.

```bash
trinity bb merge 47
trinity bb merge 47 --strategy squash --message "Squash merge: search ranking v2"
```

Options: `--message TEXT`, `--strategy merge_commit|squash|fast_forward`

### `update <pr-id>`

Update PR title or description.

```bash
trinity bb update 47 --title "Fix: search ranking improvements"
```

Options: `--title TEXT`, `--description TEXT`

### `diff <pr-id>`

Get the unified diff or diffstat for a PR.

```bash
trinity bb diff 47
trinity bb diff 47 --stat
```

Options: `--stat` (show diffstat instead of full diff)

### `activity <pr-id>`

Get the PR activity timeline (comments, approvals, commits, status changes).

```bash
trinity bb activity 47
trinity bb activity 47 --limit 20
```

Options: `--limit INT` (default 50)

---

## Confluence Commands

Full reference: [docs/confluence.md](docs/confluence.md)

```
trinity confluence <command> [options]
```

### `search <query>`

Search pages using plain text or raw CQL. Plain text is automatically wrapped as `text ~ "..."`. Pass raw CQL containing `AND`, `OR`, or `type =` and it is sent as-is.

```bash
trinity confluence search "deployment runbook"
trinity confluence search "deployment runbook" --space ENG
trinity confluence search 'title = "API Reference"' --type page
```

Options: `--space TEXT` (space key), `--type page|blogpost` (default page), `--max-results INT` (default 25)

### `get <page-id>`

Get a page by its numeric ID. Returns title, space, version, body (HTML storage format), URL, and metadata.

```bash
trinity confluence get 123456789
trinity confluence get 123456789 --no-body
trinity confluence get 123456789 --ancestors
```

Options: `--no-body` (skip body content), `--ancestors` (include parent page chain)

### `spaces`

List all accessible Confluence spaces.

```bash
trinity confluence spaces
trinity confluence spaces --search "engineering"
```

Options: `--search TEXT` (filter by name or key)

### `children <page-id>`

List direct child pages of a page.

```bash
trinity confluence children 123456789
```

### `create`

Create a new Confluence page. Body is expected in HTML storage format.

```bash
trinity confluence create \
  --space ENG \
  --title "Q2 Architecture Decision" \
  --body "<p>We decided to use PostgreSQL for the following reasons...</p>" \
  --parent 123456789
```

Options: `--space TEXT` (required), `--title TEXT` (required), `--body TEXT`, `--body-file PATH`, `--parent TEXT` (parent page ID)

### `update <page-id>`

Update an existing page. Version is auto-incremented — no need to track it manually.

```bash
trinity confluence update 123456789 --title "Updated Title"
trinity confluence update 123456789 --body-file updated_content.html
trinity confluence update 123456789 --body "<p>New content</p>" --comment "Fixed typo"
```

Options: `--title TEXT`, `--body TEXT`, `--body-file PATH`, `--comment TEXT` (version comment)

### `comment <page-id> <text>`

Add a footer comment to a Confluence page.

```bash
trinity confluence comment 123456789 "Reviewed and approved for production."
```

---

## Agent Integration

Trinity is designed to be called from agent subprocess loops. The `--json` flag produces consistent, machine-readable output for every command.

### Key Design Points

- `--json` must come **before** the subcommand: `trinity --json jira search "..."`
- Every command returns `{"error": true, "status_code": N, "message": "..."}` on failure
- Exit code is non-zero on any error — agents can check `returncode` without parsing JSON
- All timestamps are ISO 8601 strings
- Unassigned issues return `"assignee": "Unassigned"` (never `null`) in search results

### Python subprocess example

```python
import subprocess
import json


def trinity(args: list[str]) -> dict:
    result = subprocess.run(
        ["trinity", "--json"] + args,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    if result.returncode != 0 or data.get("error"):
        raise RuntimeError(f"Trinity error: {data.get('message')}")
    return data


# Search for blocked tickets
tickets = trinity(["jira", "search", "status = Blocked AND project = ECD"])
for issue in tickets["issues"]:
    print(issue["key"], issue["assignee"])

# Transition a ticket
trinity(["jira", "transition", "ECD-1448", "In Review"])

# Post a comment
trinity(["jira", "comment", "ECD-1448", "Deploying to staging now."])

# Get active sprint
sprint = trinity(["jira", "sprints", "42", "--active"])
print(sprint["sprint"]["name"])
```

### Shell / jq example

```bash
# Get all in-progress issues and extract keys
trinity --json jira search "project = ECD AND status = 'In Progress'" \
  | jq -r '.issues[].key'

# Find the active sprint ID for board 42
SPRINT_ID=$(trinity --json jira sprints 42 --active | jq '.sprint.id')

# Get sprint issues filtered to In Progress
trinity --json jira sprint-issues "$SPRINT_ID" --status "In Progress"
```

---

## Architecture

Trinity is organized into three layers:

```
src/trinity/
├── base/
│   ├── auth.py       # Credential resolution (env vars → config file → error)
│   ├── client.py     # AtlassianClient: session, retry, error mapping, pagination
│   └── exceptions.py # Typed exceptions: AuthenticationError, NotFoundError, etc.
├── jira/             # One module per Jira operation
│   ├── search.py
│   ├── get_issue.py
│   ├── get_status_history.py
│   └── ...
├── bitbucket/
│   ├── api.py        # BitbucketAPI client (wraps base client)
│   └── commands/     # One file per BB operation
│       ├── list.py
│       ├── show.py
│       └── ...
├── confluence/       # One module per Confluence operation
│   ├── search.py
│   ├── get_page.py
│   └── ...
└── cli.py            # Click group definitions and output formatting
```

**`base/auth.py`** resolves credentials for each service. For Jira and Confluence it uses the same Atlassian account (Basic Auth with email + API token). For Bitbucket it prefers a Bearer repo token and falls back to username + app password.

**`base/client.py`** provides `AtlassianClient`, a `requests.Session` with configurable retry (exponential backoff on 429 and 5xx), typed exception mapping, and a `get_all_pages()` helper for paginated Bitbucket responses.

**`bitbucket/api.py`** is a purpose-built Bitbucket API client that mirrors the Atlassian client structure but handles Bitbucket-specific patterns (Bearer token auth, `values` pagination, diffstat endpoint).

Each Jira and Confluence module is a standalone function — importable directly without going through the CLI for programmatic use:

```python
from trinity.jira.search import search_jira
from trinity.jira.get_status_history import get_status_history
from trinity.confluence.get_page import get_confluence_page

results = search_jira("project = ECD AND status = Blocked", max_results=10)
history = get_status_history("ECD-1448", all_transitions=True)
page = get_confluence_page("123456789")
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `click` | CLI framework |
| `rich` | Terminal tables and colored output |
| `requests` | HTTP client |
| `python-dotenv` | `.env` file loading |
| `pyyaml` | Config file (de)serialization |
| `gitpython` | Auto-detect Bitbucket workspace/repo from git remote |
| `python-dateutil` | Timezone-aware datetime parsing for status history |
| `pydantic` | Data validation |

---

## License

MIT
