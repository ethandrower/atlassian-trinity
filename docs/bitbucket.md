# Bitbucket Command Reference

Full reference for all `trinity bb` commands.

---

## Global Notes

- Workspace and repo are resolved in this order: `--workspace`/`--repo` flags → `BITBUCKET_WORKSPACE` env var → git remote URL auto-detection.
- When running from inside a git repository with a Bitbucket remote, `--workspace` and `--repo` can be omitted.
- Auth uses a Bearer token (`BITBUCKET_REPO_TOKEN`) with fallback to Basic Auth (`BITBUCKET_USERNAME` + `BITBUCKET_APP_PASSWORD`).
- All JSON responses include `"error": true` on failure.
- PR `show` and `list` return raw Bitbucket API objects — richer than Jira's normalized responses.

---

## Command Prefix

```bash
trinity bb [--workspace WS] [--repo REPO] <command> [options]
```

Short forms: `-w` for `--workspace`, `-r` for `--repo`.

```bash
# Explicit workspace/repo
trinity bb --workspace mycompany --repo backend list

# From a Bitbucket git repo (auto-detected)
cd ~/code/backend
trinity bb list
```

---

## `trinity bb list`

List pull requests.

```bash
trinity bb list
trinity bb list --state MERGED --limit 10
trinity bb --workspace myco --repo api list --author jsmith
trinity bb list --all   # Fetch all pages (no limit)
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--state TEXT` | OPEN | `OPEN`, `MERGED`, or `DECLINED` |
| `--author TEXT` | — | Filter by author username |
| `--limit INT` | 25 | Max results per page |
| `--all` | false | Fetch all pages (auto-pagination) |

**JSON response:**

```json
[
  {
    "id": 47,
    "title": "Add search ranking improvements",
    "description": "Implements TF-IDF scoring for the abstract search module.",
    "state": "OPEN",
    "author": {
      "display_name": "Mohamed Belkahla",
      "nickname": "mbelkahla",
      "uuid": "{f3b4c2a1-8e91-4b5d-a234-bc1234567890}"
    },
    "source": {
      "branch": {"name": "feature/search-ranking"},
      "commit": {"hash": "a1b2c3d4e5f6"}
    },
    "destination": {
      "branch": {"name": "main"}
    },
    "reviewers": [
      {
        "display_name": "Sarah Chen",
        "nickname": "schen",
        "uuid": "{a9b8c7d6-5432-10fe-dcba-0987654321ab}"
      }
    ],
    "participants": [
      {
        "user": {"display_name": "Sarah Chen", "nickname": "schen"},
        "role": "REVIEWER",
        "approved": false,
        "state": "unapproved"
      }
    ],
    "created_on": "2026-03-09T10:00:00.000000+00:00",
    "updated_on": "2026-03-10T14:23:00.000000+00:00",
    "comment_count": 3,
    "task_count": 1,
    "links": {
      "html": {"href": "https://bitbucket.org/myco/backend/pull-requests/47"}
    }
  }
]
```

Human output (without `--json`):

```
┌────┬──────────────────────────────────────┬──────────────────┬───────┬────────────┐
│ ID │ Title                                │ Author           │ State │ Created    │
├────┼──────────────────────────────────────┼──────────────────┼───────┼────────────┤
│ 47 │ Add search ranking improvements      │ Mohamed Belkahla │ OPEN  │ 2026-03-09 │
│ 46 │ Fix: pagination reset on filter chan │ David Park       │ OPEN  │ 2026-03-07 │
└────┴──────────────────────────────────────┴──────────────────┴───────┴────────────┘
```

---

## `trinity bb show <pr-id>`

Show full PR details. Always outputs JSON.

```bash
trinity bb show 47
trinity bb show 47 --comments
```

**Options:**

| Flag | Description |
|------|-------------|
| `--comments` | Include all PR comments |

**JSON response (raw Bitbucket object):**

```json
{
  "id": 47,
  "title": "Add search ranking improvements",
  "description": "Implements TF-IDF scoring for the abstract search module.\n\nJira: ECD-1392",
  "state": "OPEN",
  "author": {
    "display_name": "Mohamed Belkahla",
    "nickname": "mbelkahla",
    "uuid": "{f3b4c2a1-8e91-4b5d-a234-bc1234567890}",
    "links": {
      "avatar": {"href": "https://secure.gravatar.com/avatar/..."}
    }
  },
  "source": {
    "branch": {"name": "feature/search-ranking"},
    "commit": {"hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"}
  },
  "destination": {
    "branch": {"name": "main"},
    "commit": {"hash": "f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5"}
  },
  "reviewers": [
    {
      "display_name": "Sarah Chen",
      "nickname": "schen",
      "uuid": "{a9b8c7d6-5432-10fe-dcba-0987654321ab}"
    }
  ],
  "participants": [
    {
      "user": {
        "display_name": "Sarah Chen",
        "nickname": "schen"
      },
      "role": "REVIEWER",
      "approved": false,
      "state": "unapproved"
    }
  ],
  "created_on": "2026-03-09T10:00:00.000000+00:00",
  "updated_on": "2026-03-10T14:23:00.000000+00:00",
  "comment_count": 3,
  "task_count": 1,
  "merge_commit": null,
  "close_source_branch": false,
  "links": {
    "html": {"href": "https://bitbucket.org/myco/backend/pull-requests/47"},
    "commits": {"href": "https://api.bitbucket.org/2.0/repositories/myco/backend/pullrequests/47/commits"},
    "diff": {"href": "https://api.bitbucket.org/2.0/repositories/myco/backend/pullrequests/47/diff"}
  },
  "comments": [
    {
      "id": 891,
      "content": {"raw": "Have you considered caching the TF-IDF scores?"},
      "author": {
        "display_name": "Sarah Chen",
        "nickname": "schen"
      },
      "created_on": "2026-03-10T09:15:00.000000+00:00",
      "updated_on": "2026-03-10T09:15:00.000000+00:00",
      "inline": null,
      "parent": null
    }
  ]
}
```

---

## `trinity bb create`

Create a pull request. Source branch defaults to the current git branch.

```bash
trinity bb create \
  --title "Add search ranking improvements" \
  --source feature/search-ranking \
  --destination main \
  --reviewers schen,dpark
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--title TEXT` | `PR from <branch>` | PR title |
| `--description TEXT` | — | PR description |
| `--source TEXT` | current git branch | Source branch name |
| `--destination TEXT` | main | Target branch name |
| `--reviewers TEXT` | — | Comma-separated Bitbucket usernames |

**JSON response (raw Bitbucket PR object):**

```json
{
  "id": 48,
  "title": "Add search ranking improvements",
  "description": "",
  "state": "OPEN",
  "author": {
    "display_name": "Mohamed Belkahla",
    "nickname": "mbelkahla"
  },
  "source": {
    "branch": {"name": "feature/search-ranking"}
  },
  "destination": {
    "branch": {"name": "main"}
  },
  "created_on": "2026-03-11T09:00:00.000000+00:00",
  "updated_on": "2026-03-11T09:00:00.000000+00:00",
  "links": {
    "html": {"href": "https://bitbucket.org/myco/backend/pull-requests/48"}
  }
}
```

---

## `trinity bb comment <pr-id>`

Add a comment to a PR. Supports inline comments on specific files/lines and replies to existing comments.

```bash
trinity bb comment 47 --message "LGTM, nice work."
trinity bb comment 47 --message "Consider extracting this into a utility function." \
  --file src/search/ranking.py --line 87
trinity bb comment 47 --message "Good point, I'll refactor that." --reply-to 891
```

**Options:**

| Flag | Description |
|------|-------------|
| `--message/-m TEXT` | Comment text (required) |
| `--file TEXT` | File path for an inline comment |
| `--line INT` | Line number for the inline comment |
| `--reply-to INT` | Comment ID to reply to |

**JSON response:**

```json
{
  "id": 924,
  "content": {"raw": "LGTM, nice work."},
  "author": {
    "display_name": "Remington Bot",
    "nickname": "remington-bot"
  },
  "created_on": "2026-03-11T09:05:00.000000+00:00",
  "updated_on": "2026-03-11T09:05:00.000000+00:00",
  "inline": null,
  "parent": null
}
```

---

## `trinity bb approve <pr-id>`

Approve a pull request.

```bash
trinity bb approve 47
```

**JSON response:**

```json
{
  "approved": true,
  "user": {
    "display_name": "Remington Bot",
    "nickname": "remington-bot",
    "uuid": "{bot-uuid}"
  },
  "state": "approved"
}
```

---

## `trinity bb decline <pr-id>`

Decline a pull request.

```bash
trinity bb decline 47
```

**JSON response:**

```json
{
  "id": 47,
  "state": "DECLINED",
  "title": "Add search ranking improvements",
  "updated_on": "2026-03-11T09:10:00.000000+00:00"
}
```

---

## `trinity bb merge <pr-id>`

Merge a pull request.

```bash
trinity bb merge 47
trinity bb merge 47 --strategy squash --message "feat: search ranking improvements (#47)"
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--message TEXT` | — | Custom merge commit message |
| `--strategy TEXT` | (Bitbucket default) | `merge_commit`, `squash`, or `fast_forward` |

**JSON response:**

```json
{
  "id": 47,
  "state": "MERGED",
  "title": "Add search ranking improvements",
  "merge_commit": {
    "hash": "deadbeef1234abcd5678ef901234abcd5678ef90"
  },
  "closed_on": "2026-03-11T09:15:00.000000+00:00",
  "updated_on": "2026-03-11T09:15:00.000000+00:00"
}
```

---

## `trinity bb update <pr-id>`

Update a PR's title or description.

```bash
trinity bb update 47 --title "feat: TF-IDF search ranking improvements"
trinity bb update 47 --description "Updated description with benchmark results."
```

**Options:**

| Flag | Description |
|------|-------------|
| `--title TEXT` | New PR title |
| `--description TEXT` | New PR description |

**JSON response (raw Bitbucket PR object):**

```json
{
  "id": 47,
  "title": "feat: TF-IDF search ranking improvements",
  "description": "Updated description with benchmark results.",
  "state": "OPEN",
  "updated_on": "2026-03-11T09:20:00.000000+00:00"
}
```

---

## `trinity bb diff <pr-id>`

Get the unified diff or diffstat for a PR.

```bash
trinity bb diff 47          # Full unified diff (text output)
trinity bb diff 47 --stat   # Diffstat JSON
```

**Options:**

| Flag | Description |
|------|-------------|
| `--stat` | Return diffstat instead of full diff |

**Text output (default — raw unified diff):**

```
diff --git a/src/search/ranking.py b/src/search/ranking.py
index a1b2c3d..f4e5d6c 100644
--- a/src/search/ranking.py
+++ b/src/search/ranking.py
@@ -10,6 +10,18 @@ class SearchRanker:
     def __init__(self):
         self.index = {}

+    def compute_tfidf(self, documents: list[str]) -> dict:
+        """Compute TF-IDF scores for a corpus of documents."""
+        tf = self._term_frequency(documents)
+        idf = self._inverse_document_frequency(documents)
+        return {term: tf[term] * idf[term] for term in tf}
+
     def rank(self, query: str, results: list) -> list:
```

**JSON response with `--stat`:**

```json
{
  "values": [
    {
      "type": "modified",
      "old": {
        "path": "src/search/ranking.py",
        "lines_removed": 4
      },
      "new": {
        "path": "src/search/ranking.py",
        "lines_added": 22
      },
      "lines_added": 22,
      "lines_removed": 4
    },
    {
      "type": "added",
      "old": null,
      "new": {
        "path": "tests/test_ranking.py",
        "lines_added": 45
      },
      "lines_added": 45,
      "lines_removed": 0
    }
  ]
}
```

---

## `trinity bb activity <pr-id>`

Get the PR activity timeline — comments, approvals, commits pushed, and status changes.

```bash
trinity bb activity 47
trinity bb activity 47 --limit 20
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--limit INT` | 50 | Maximum activity events to return |

**JSON response:**

```json
[
  {
    "comment": {
      "id": 891,
      "content": {"raw": "Have you considered caching the TF-IDF scores?"},
      "author": {"display_name": "Sarah Chen", "nickname": "schen"},
      "created_on": "2026-03-10T09:15:00.000000+00:00"
    }
  },
  {
    "approval": {
      "date": "2026-03-10T15:00:00.000000+00:00",
      "user": {"display_name": "Sarah Chen", "nickname": "schen"}
    }
  },
  {
    "update": {
      "state": "OPEN",
      "title": "Add search ranking improvements",
      "description": "Implements TF-IDF scoring...",
      "author": {"display_name": "Mohamed Belkahla", "nickname": "mbelkahla"},
      "date": "2026-03-09T10:00:00.000000+00:00",
      "commits": [
        {
          "hash": "a1b2c3d4",
          "message": "feat: add TF-IDF scoring module",
          "author": {"raw": "Mohamed Belkahla <m@company.com>"},
          "date": "2026-03-09T09:58:00+00:00"
        }
      ]
    }
  }
]
```
