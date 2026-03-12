# Jira Command Reference

Full reference for all `trinity jira` commands. Every command outputs JSON when invoked with `trinity --json jira ...`.

---

## Global Notes

- All JSON responses include `"error": true` on failure with `"status_code"` and `"message"` fields.
- Timestamps are ISO 8601 strings with timezone offset.
- `"assignee"` in search results is always a string (`"Unassigned"` if unset); in `show` it is an object.
- Boards/sprints use the Jira Agile API — requires a personal API token; service accounts may lack scope.

---

## `trinity jira search <jql>`

Search Jira issues using JQL.

```bash
trinity jira search "project = ECD AND status = 'In Progress'"
trinity jira search "assignee = currentUser() AND sprint in openSprints()" --max-results 10
trinity --json jira search "project = ECD AND priority = Highest" --max-results 2
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--max-results INT` | 50 | Maximum issues to return (capped at 100) |
| `--fields TEXT` | (standard set) | Comma-separated field list to include |

**JSON response:**

```json
{
  "total": 42,
  "count": 2,
  "issues": [
    {
      "key": "ECD-1448",
      "id": "10482",
      "summary": "Redesign Abstract Screening interface",
      "status": "In Progress",
      "assignee": "Mohamed Belkahla",
      "assignee_id": "557058:f3b4c2a1-8e91-4b5d-a234-bc1234567890",
      "reporter": "Sarah Chen",
      "priority": "Highest",
      "type": "Story",
      "labels": ["frontend", "ux"],
      "created": "2026-02-10T09:00:00.000+0000",
      "updated": "2026-03-10T14:23:00.000+0000"
    },
    {
      "key": "ECD-1392",
      "id": "10436",
      "summary": "Fix search ranking algorithm",
      "status": "In Progress",
      "assignee": "David Park",
      "assignee_id": "557058:a1b2c3d4-5678-9012-ef34-567890abcdef",
      "reporter": "Mohamed Belkahla",
      "priority": "High",
      "type": "Bug",
      "labels": ["backend"],
      "created": "2026-01-28T11:30:00.000+0000",
      "updated": "2026-03-09T16:45:00.000+0000"
    }
  ]
}
```

**Error response:**

```json
{
  "error": true,
  "status_code": 400,
  "message": "The value 'In Progres' does not exist for the field 'status'."
}
```

---

## `trinity jira show <issue-key>`

Get full details of a Jira issue. Always outputs JSON regardless of `--json` flag.

```bash
trinity jira show ECD-1448
trinity jira show ECD-1448 --comments
```

**Options:**

| Flag | Description |
|------|-------------|
| `--comments` | Include the last 20 comments |

**JSON response:**

```json
{
  "key": "ECD-1448",
  "id": "10482",
  "self": "https://api.atlassian.com/ex/jira/abc123/rest/api/3/issue/10482",
  "summary": "Redesign Abstract Screening interface",
  "description": "The current abstract screening UI needs a full redesign to support the new workflow. See Figma link for mockups.",
  "status": "In Progress",
  "status_category": "In Progress",
  "assignee": {
    "name": "Mohamed Belkahla",
    "account_id": "557058:f3b4c2a1-8e91-4b5d-a234-bc1234567890",
    "email": "mohamed@company.com"
  },
  "reporter": {
    "name": "Sarah Chen",
    "account_id": "557058:a9b8c7d6-5432-10fe-dcba-0987654321ab"
  },
  "priority": "Highest",
  "type": "Story",
  "labels": ["frontend", "ux"],
  "created": "2026-02-10T09:00:00.000+0000",
  "updated": "2026-03-10T14:23:00.000+0000",
  "resolution": null,
  "sprint": {
    "id": 188,
    "name": "Sprint 24",
    "state": "active"
  },
  "epic_key": "ECD-1200",
  "story_points": 8,
  "comments": [
    {
      "id": "20041",
      "author": "Sarah Chen",
      "author_id": "557058:a9b8c7d6-5432-10fe-dcba-0987654321ab",
      "body": "Figma file has been updated with the latest mockups.",
      "created": "2026-03-08T10:15:00.000+0000",
      "updated": "2026-03-08T10:15:00.000+0000"
    },
    {
      "id": "20089",
      "author": "Mohamed Belkahla",
      "author_id": "557058:f3b4c2a1-8e91-4b5d-a234-bc1234567890",
      "body": "PR #47 is up for review.",
      "created": "2026-03-10T14:23:00.000+0000",
      "updated": "2026-03-10T14:23:00.000+0000"
    }
  ]
}
```

---

## `trinity jira comment <issue-key> <text>`

Add an ADF comment to an issue. Supports @-mentions by account ID.

```bash
trinity jira comment ECD-1448 "PR is merged and deployed to staging."
trinity jira comment ECD-1448 "Hey @Mohamed, can you take a look?" \
  --mention 557058:f3b4c2a1-8e91-4b5d-a234-bc1234567890 "Mohamed Belkahla"
```

**Options:**

| Flag | Description |
|------|-------------|
| `--mention ACCOUNT_ID NAME` | Add a mention. Replaces `@Name` placeholder in text. Repeatable. |

**JSON response (success):**

```json
{
  "id": "20102",
  "issue_key": "ECD-1448",
  "author": "Remington Bot",
  "created": "2026-03-11T09:00:00.000+0000"
}
```

---

## `trinity jira transition <issue-key> <transition-name>`

Move an issue to a new status. Transition name is case-insensitive and supports partial matches.

```bash
trinity jira transition ECD-1448 "In Review"
trinity jira transition ECD-1448 --id 31
trinity jira transition ECD-1448 "Done" --comment "All comments addressed, merged."
```

**Options:**

| Flag | Description |
|------|-------------|
| `--id TEXT` | Transition by ID instead of name |
| `--comment TEXT` | Comment to post during the transition |

**JSON response (success):**

```json
{
  "success": true,
  "issue_key": "ECD-1448",
  "transition": "In Review"
}
```

---

## `trinity jira transitions <issue-key>`

List all available status transitions for an issue.

```bash
trinity jira transitions ECD-1448
```

**JSON response:**

```json
{
  "issue_key": "ECD-1448",
  "current_status": "In Progress",
  "transitions": [
    {
      "id": "11",
      "name": "To Do",
      "to_status": "To Do"
    },
    {
      "id": "21",
      "name": "In Review",
      "to_status": "In Review"
    },
    {
      "id": "31",
      "name": "Done",
      "to_status": "Done"
    },
    {
      "id": "41",
      "name": "Blocked",
      "to_status": "Blocked"
    }
  ]
}
```

---

## `trinity jira edit <issue-key>`

Update fields on an issue. At least one field flag is required.

```bash
trinity jira edit ECD-1448 --priority High
trinity jira edit ECD-1448 --summary "Redesign Abstract Screening (v2)"
trinity jira edit ECD-1448 --assignee 557058:f3b4c2a1-8e91-4b5d-a234-bc1234567890
trinity jira edit ECD-1448 --labels "frontend,ux,critical"
trinity jira edit ECD-1448 --add-labels "urgent" --remove-labels "draft"
trinity jira edit ECD-1448 --assignee none   # Unassign
```

**Options:**

| Flag | Description |
|------|-------------|
| `--summary TEXT` | New issue title |
| `--priority TEXT` | Priority name (Highest, High, Medium, Low, Lowest) |
| `--assignee TEXT` | Account ID. Use `"none"` to unassign. |
| `--labels TEXT` | Comma-separated list — **replaces** all existing labels |
| `--add-labels TEXT` | Comma-separated labels to add |
| `--remove-labels TEXT` | Comma-separated labels to remove |

**JSON response (success):**

```json
{
  "success": true,
  "issue_key": "ECD-1448",
  "updated_fields": ["priority"]
}
```

---

## `trinity jira status-history <issue-key>`

Time-in-status analysis. Calculates how long the issue has been in its current status and optionally shows full transition history.

```bash
trinity jira status-history ECD-1448
trinity jira status-history ECD-1448 --target-status "In Review"
trinity jira status-history ECD-1448 --all-transitions
```

**Options:**

| Flag | Description |
|------|-------------|
| `--target-status TEXT` | Return analysis for a specific status (when did it enter, how long it was there) |
| `--all-transitions` | Include the full chronological list of status changes |

**JSON response (default):**

```json
{
  "issue_key": "ECD-1448",
  "current_status": "In Progress",
  "current_status_category": "In Progress",
  "entered_current_status": "2026-03-05T09:30:00.000+0000",
  "time_in_current_status_hours": 147.92,
  "time_in_current_status_days": 6.16
}
```

**With `--target-status "In Review"`:**

```json
{
  "issue_key": "ECD-1448",
  "current_status": "In Progress",
  "current_status_category": "In Progress",
  "entered_current_status": "2026-03-05T09:30:00.000+0000",
  "time_in_current_status_hours": 147.92,
  "time_in_current_status_days": 6.16,
  "target_status_info": {
    "status": "In Review",
    "entered_at": "2026-02-20T10:00:00.000+0000",
    "exited_at": "2026-02-22T14:30:00.000+0000",
    "still_in_status": false,
    "hours_in_status": 52.5,
    "days_in_status": 2.19
  }
}
```

**With `--all-transitions`:**

```json
{
  "issue_key": "ECD-1448",
  "current_status": "In Progress",
  "current_status_category": "In Progress",
  "entered_current_status": "2026-03-05T09:30:00.000+0000",
  "time_in_current_status_hours": 147.92,
  "time_in_current_status_days": 6.16,
  "status_history": [
    {
      "from_status": null,
      "to_status": "To Do",
      "changed_at": "2026-02-10T09:00:00.000+0000",
      "changed_by": "Sarah Chen"
    },
    {
      "from_status": "To Do",
      "to_status": "In Progress",
      "changed_at": "2026-02-15T10:00:00.000+0000",
      "changed_by": "Mohamed Belkahla"
    },
    {
      "from_status": "In Progress",
      "to_status": "In Review",
      "changed_at": "2026-02-20T10:00:00.000+0000",
      "changed_by": "Mohamed Belkahla"
    },
    {
      "from_status": "In Review",
      "to_status": "In Progress",
      "changed_at": "2026-03-05T09:30:00.000+0000",
      "changed_by": "Sarah Chen"
    }
  ]
}
```

---

## `trinity jira user <query>`

Look up a Jira user by name or email. Returns account IDs for use with `edit --assignee` and `comment --mention`.

```bash
trinity jira user "john smith"
trinity jira user "sarah@company.com" --max-results 1
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--max-results INT` | 10 | Maximum users to return |

**JSON response:**

```json
{
  "count": 2,
  "users": [
    {
      "account_id": "557058:f3b4c2a1-8e91-4b5d-a234-bc1234567890",
      "display_name": "John Smith",
      "email": "john@company.com",
      "active": true,
      "account_type": "atlassian"
    },
    {
      "account_id": "557058:11223344-5566-7788-99aa-bbccddeeff00",
      "display_name": "John Smythe",
      "email": "jsmythe@company.com",
      "active": true,
      "account_type": "atlassian"
    }
  ]
}
```

> **Note:** Users with private profiles won't appear in API search results. Look them up manually via `home.atlassian.com → Teams → People` and copy the ID from the URL after `/people/`.

---

## `trinity jira projects`

List all visible Jira projects.

```bash
trinity jira projects
trinity jira projects --search "eng"
```

**Options:**

| Flag | Description |
|------|-------------|
| `--search TEXT` | Filter by project name or key |

**JSON response:**

```json
{
  "count": 3,
  "projects": [
    {
      "id": "10001",
      "key": "ECD",
      "name": "Engineering Core Development",
      "type": "software",
      "style": "next-gen",
      "lead": "Sarah Chen"
    },
    {
      "id": "10002",
      "key": "OPS",
      "name": "Operations",
      "type": "service_desk",
      "style": "classic",
      "lead": "Alex Johnson"
    }
  ]
}
```

---

## `trinity jira boards`

List Jira Agile boards.

```bash
trinity jira boards
trinity jira boards --project ECD --type scrum
```

**Options:**

| Flag | Description |
|------|-------------|
| `--project TEXT` | Filter by project key |
| `--type scrum\|kanban` | Filter by board type |

**JSON response:**

```json
{
  "count": 2,
  "boards": [
    {
      "id": 42,
      "name": "ECD Scrum Board",
      "type": "scrum",
      "project_key": "ECD",
      "project_name": "Engineering Core Development"
    },
    {
      "id": 43,
      "name": "Design Kanban",
      "type": "kanban",
      "project_key": "ECD",
      "project_name": "Engineering Core Development"
    }
  ]
}
```

---

## `trinity jira sprints <board-id>`

List sprints for a board.

```bash
trinity jira sprints 42
trinity jira sprints 42 --state active
trinity jira sprints 42 --active   # Returns single sprint object
```

**Options:**

| Flag | Description |
|------|-------------|
| `--state active\|closed\|future` | Filter by sprint state |
| `--active` | Return the single active sprint as a top-level object |

**JSON response (list):**

```json
{
  "board_id": 42,
  "count": 3,
  "sprints": [
    {
      "id": 186,
      "name": "Sprint 22",
      "state": "closed",
      "start_date": "2026-01-13T09:00:00.000Z",
      "end_date": "2026-01-24T18:00:00.000Z",
      "complete_date": "2026-01-24T18:30:00.000Z",
      "goal": "Complete authentication refactor"
    },
    {
      "id": 187,
      "name": "Sprint 23",
      "state": "closed",
      "start_date": "2026-01-27T09:00:00.000Z",
      "end_date": "2026-02-07T18:00:00.000Z",
      "complete_date": "2026-02-07T18:15:00.000Z",
      "goal": "Launch search improvements"
    },
    {
      "id": 188,
      "name": "Sprint 24",
      "state": "active",
      "start_date": "2026-02-24T09:00:00.000Z",
      "end_date": "2026-03-14T18:00:00.000Z",
      "complete_date": null,
      "goal": "Abstract screening redesign + onboarding flow"
    }
  ]
}
```

**JSON response (`--active`):**

```json
{
  "found": true,
  "sprint": {
    "id": 188,
    "name": "Sprint 24",
    "state": "active",
    "start_date": "2026-02-24T09:00:00.000Z",
    "end_date": "2026-03-14T18:00:00.000Z",
    "complete_date": null,
    "goal": "Abstract screening redesign + onboarding flow"
  }
}
```

---

## `trinity jira sprint-issues <sprint-id>`

Get issues in a sprint.

```bash
trinity jira sprint-issues 188
trinity jira sprint-issues 188 --status "In Progress"
trinity jira sprint-issues 188 --completed-only --max-results 50
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--status TEXT` | (all) | Filter by exact status name |
| `--completed-only` | false | Return only Done/Complete issues |
| `--max-results INT` | 100 | Maximum issues to return |

**JSON response:**

```json
{
  "sprint_id": 188,
  "total": 24,
  "count": 24,
  "issues": [
    {
      "key": "ECD-1448",
      "id": "10482",
      "summary": "Redesign Abstract Screening interface",
      "status": "In Progress",
      "assignee": "Mohamed Belkahla",
      "assignee_id": "557058:f3b4c2a1-8e91-4b5d-a234-bc1234567890",
      "priority": "Highest",
      "type": "Story",
      "story_points": 8,
      "labels": ["frontend", "ux"],
      "updated": "2026-03-10T14:23:00.000+0000"
    },
    {
      "key": "ECD-1461",
      "id": "10495",
      "summary": "Write unit tests for search module",
      "status": "To Do",
      "assignee": "David Park",
      "assignee_id": "557058:a1b2c3d4-5678-9012-ef34-567890abcdef",
      "priority": "Medium",
      "type": "Task",
      "story_points": 3,
      "labels": [],
      "updated": "2026-03-07T10:00:00.000+0000"
    }
  ]
}
```

---

## `trinity jira worklogs <issue-key>`

Get time-tracking worklogs for an issue. Fetches all pages automatically.

```bash
trinity jira worklogs ECD-1448
trinity jira worklogs ECD-1448 --days 7
```

**Options:**

| Flag | Description |
|------|-------------|
| `--days INT` | Only return worklogs from the last N days |

**JSON response:**

```json
{
  "issue_key": "ECD-1448",
  "total": 3,
  "total_seconds": 25200,
  "worklogs": [
    {
      "id": "50123",
      "author": "Mohamed Belkahla",
      "author_id": "557058:f3b4c2a1-8e91-4b5d-a234-bc1234567890",
      "started": "2026-03-06T10:00:00.000+0000",
      "time_spent": "3h",
      "time_spent_seconds": 10800,
      "comment": "Initial layout implementation"
    },
    {
      "id": "50198",
      "author": "Mohamed Belkahla",
      "author_id": "557058:f3b4c2a1-8e91-4b5d-a234-bc1234567890",
      "started": "2026-03-09T14:00:00.000+0000",
      "time_spent": "4h",
      "time_spent_seconds": 14400,
      "comment": "Responsive design and QA fixes"
    },
    {
      "id": "50241",
      "author": "Mohamed Belkahla",
      "author_id": "557058:f3b4c2a1-8e91-4b5d-a234-bc1234567890",
      "started": "2026-03-10T09:00:00.000+0000",
      "time_spent": "0h",
      "time_spent_seconds": 0,
      "comment": ""
    }
  ]
}
```

---

## `trinity jira release-issues`

Get completed issues grouped by type — useful for generating release notes.

```bash
trinity jira release-issues --project ECD --days 14
trinity jira release-issues --fix-version "v2.1.0"
trinity jira release-issues --current-sprint
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--project TEXT` | ECD | Jira project key |
| `--days INT` | 14 | Look back N days (used when no version/sprint specified) |
| `--fix-version TEXT` | — | Filter by fix version name |
| `--current-sprint` | false | Use the currently active sprint |

**JSON response:**

```json
{
  "jql": "project = ECD AND statusCategory = Done AND status CHANGED TO Complete AFTER -14d AND issuetype NOT IN (\"Sub-task\", \"Epic\") ORDER BY updated DESC",
  "total": 12,
  "count": 12,
  "issues": [
    {
      "key": "ECD-1430",
      "id": "10464",
      "summary": "Add CSV export to search results",
      "description": "Users can now export up to 1000 search results as a CSV file.",
      "status": "Done",
      "type": "Story",
      "assignee": "David Park",
      "priority": "High",
      "story_points": 5,
      "labels": ["feature", "export"],
      "fix_versions": ["v2.1.0"],
      "updated": "2026-03-09T16:00:00.000+0000"
    }
  ],
  "by_type": {
    "Story": [
      {
        "key": "ECD-1430",
        "summary": "Add CSV export to search results",
        "assignee": "David Park",
        "story_points": 5
      }
    ],
    "Bug": [
      {
        "key": "ECD-1421",
        "summary": "Fix pagination resetting on filter change",
        "assignee": "Sarah Chen",
        "story_points": 2
      }
    ],
    "Task": [
      {
        "key": "ECD-1418",
        "summary": "Upgrade Django to 5.0",
        "assignee": "David Park",
        "story_points": 3
      }
    ]
  }
}
```
