# Confluence Command Reference

Full reference for all `trinity confluence` commands.

---

## Global Notes

- Confluence uses the same Atlassian credentials as Jira (`ATLASSIAN_EMAIL` + `ATLASSIAN_API_TOKEN`).
- Page IDs are numeric strings (e.g., `"123456789"`).
- `confluence search` auto-detects plain text vs. raw CQL — wrap in quotes for phrases.
- `confluence update` auto-fetches the current page version; you never need to track it manually.
- Body content uses **HTML storage format** (Confluence's internal representation), not Markdown.
- All JSON responses include `"error": true` on failure with `"status_code"` and `"message"`.

---

## `trinity confluence search <query>`

Search Confluence pages using plain text or raw CQL (Confluence Query Language).

Plain text is automatically wrapped as `text ~ "..."`. If the query contains `AND`, `OR`, or starts with `type =`, it is sent as raw CQL.

```bash
trinity confluence search "deployment runbook"
trinity confluence search "API authentication" --space ENG --max-results 5
trinity confluence search "deployment runbook" --type blogpost
trinity confluence search 'title = "API Reference" AND space = "ENG"'
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--space TEXT` | — | Limit to a specific space key |
| `--type page\|blogpost` | page | Content type to search |
| `--max-results INT` | 25 | Maximum results (capped at 50) |

**JSON response:**

```json
{
  "cql": "text ~ \"deployment runbook\" AND type = \"page\" ORDER BY lastmodified DESC",
  "total": 4,
  "count": 4,
  "results": [
    {
      "id": "123456789",
      "title": "Production Deployment Runbook",
      "type": "page",
      "status": "current",
      "space_key": "ENG",
      "space_name": "Engineering",
      "url": "https://myco.atlassian.net/wiki/spaces/ENG/pages/123456789/Production+Deployment+Runbook",
      "updated": "2026-03-01T14:30:00.000Z",
      "author": "Sarah Chen",
      "excerpt": "...steps to deploy the backend service to production. Run <code>make deploy ENV=prod</code>..."
    },
    {
      "id": "987654321",
      "title": "Staging Deployment Guide",
      "type": "page",
      "status": "current",
      "space_key": "ENG",
      "space_name": "Engineering",
      "url": "https://myco.atlassian.net/wiki/spaces/ENG/pages/987654321/Staging+Deployment+Guide",
      "updated": "2026-02-15T10:00:00.000Z",
      "author": "David Park",
      "excerpt": "...deploy to staging using the CI pipeline or manually via the deployment runbook..."
    }
  ]
}
```

Human output (without `--json`):

```
┌───────────┬──────────────────────────────┬───────┬────────────┐
│ ID        │ Title                        │ Space │ Updated    │
├───────────┼──────────────────────────────┼───────┼────────────┤
│ 123456789 │ Production Deployment Runbook│ ENG   │ 2026-03-01 │
│ 987654321 │ Staging Deployment Guide     │ ENG   │ 2026-02-15 │
└───────────┴──────────────────────────────┴───────┴────────────┘
```

---

## `trinity confluence get <page-id>`

Get a page by its numeric ID. Returns title, space, version, author, body (HTML storage format), and URL.

```bash
trinity confluence get 123456789
trinity confluence get 123456789 --no-body    # Metadata only
trinity confluence get 123456789 --ancestors  # Include parent page chain
```

**Options:**

| Flag | Description |
|------|-------------|
| `--no-body` | Exclude body content (faster for metadata-only lookups) |
| `--ancestors` | Include the chain of parent pages |

**JSON response:**

```json
{
  "id": "123456789",
  "title": "Production Deployment Runbook",
  "status": "current",
  "space_key": "ENG",
  "space_name": "Engineering",
  "version": 14,
  "body": "<h2>Overview</h2><p>This runbook covers all steps required to deploy the backend service to production.</p><h2>Pre-deployment Checklist</h2><ul><li>All tests passing in CI</li><li>Staging smoke tests completed</li><li>On-call engineer notified</li></ul>",
  "url": "https://myco.atlassian.net/wiki/spaces/ENG/pages/123456789/Production+Deployment+Runbook",
  "created": null,
  "updated": "2026-03-01T14:30:00.000Z",
  "author": "Sarah Chen",
  "ancestors": []
}
```

**With `--ancestors`:**

```json
{
  "id": "123456789",
  "title": "Production Deployment Runbook",
  "status": "current",
  "space_key": "ENG",
  "space_name": "Engineering",
  "version": 14,
  "body": "<h2>Overview</h2>...",
  "url": "https://myco.atlassian.net/wiki/spaces/ENG/pages/123456789",
  "updated": "2026-03-01T14:30:00.000Z",
  "author": "Sarah Chen",
  "ancestors": [
    {"id": "100000001", "title": "Engineering"},
    {"id": "100000002", "title": "Operations"},
    {"id": "100000003", "title": "Runbooks"}
  ]
}
```

**With `--no-body`:**

```json
{
  "id": "123456789",
  "title": "Production Deployment Runbook",
  "status": "current",
  "space_key": "ENG",
  "space_name": "Engineering",
  "version": 14,
  "body": null,
  "url": "https://myco.atlassian.net/wiki/spaces/ENG/pages/123456789",
  "updated": "2026-03-01T14:30:00.000Z",
  "author": "Sarah Chen",
  "ancestors": []
}
```

---

## `trinity confluence spaces`

List all Confluence spaces accessible with the current credentials.

```bash
trinity confluence spaces
trinity confluence spaces --search "engineering"
```

**Options:**

| Flag | Description |
|------|-------------|
| `--search TEXT` | Filter by space name or key (case-insensitive) |

**JSON response:**

```json
{
  "count": 4,
  "spaces": [
    {
      "id": "557058",
      "key": "ENG",
      "name": "Engineering",
      "type": "global",
      "status": "current",
      "url": "https://myco.atlassian.net/wiki/spaces/ENG"
    },
    {
      "id": "557059",
      "key": "PROD",
      "name": "Product",
      "type": "global",
      "status": "current",
      "url": "https://myco.atlassian.net/wiki/spaces/PROD"
    },
    {
      "id": "557060",
      "key": "~john.smith",
      "name": "John Smith",
      "type": "personal",
      "status": "current",
      "url": "https://myco.atlassian.net/wiki/spaces/~john.smith"
    },
    {
      "id": "557061",
      "key": "ARCH",
      "name": "Architecture",
      "type": "global",
      "status": "current",
      "url": "https://myco.atlassian.net/wiki/spaces/ARCH"
    }
  ]
}
```

---

## `trinity confluence children <page-id>`

List the direct child pages of a page.

```bash
trinity confluence children 123456789
```

**JSON response:**

```json
{
  "parent_id": "123456789",
  "count": 3,
  "children": [
    {
      "id": "200000001",
      "title": "Backend Deployment",
      "status": "current",
      "url": "https://myco.atlassian.net/wiki/spaces/ENG/pages/200000001/Backend+Deployment"
    },
    {
      "id": "200000002",
      "title": "Frontend Deployment",
      "status": "current",
      "url": "https://myco.atlassian.net/wiki/spaces/ENG/pages/200000002/Frontend+Deployment"
    },
    {
      "id": "200000003",
      "title": "Database Migration Runbook",
      "status": "current",
      "url": "https://myco.atlassian.net/wiki/spaces/ENG/pages/200000003/Database+Migration+Runbook"
    }
  ]
}
```

---

## `trinity confluence create`

Create a new Confluence page. Body must be in HTML storage format. Supply body inline with `--body` or from a file with `--body-file`.

```bash
trinity confluence create \
  --space ENG \
  --title "Q2 Architecture Decision: PostgreSQL" \
  --body "<h2>Decision</h2><p>We will use PostgreSQL for the new reporting service.</p><h2>Rationale</h2><ul><li>Existing team expertise</li><li>JSONB support for flexible schema</li></ul>"

# From file
trinity confluence create \
  --space ENG \
  --title "Sprint 25 Retrospective" \
  --body-file retro.html \
  --parent 123456789
```

**Options:**

| Flag | Description |
|------|-------------|
| `--space TEXT` | Space key (required) |
| `--title TEXT` | Page title (required) |
| `--body TEXT` | Page body in HTML storage format |
| `--body-file PATH` | Read body from a file |
| `--parent TEXT` | Parent page ID |

**JSON response:**

```json
{
  "id": "300000001",
  "title": "Q2 Architecture Decision: PostgreSQL",
  "status": "current",
  "space_key": "ENG",
  "space_name": "Engineering",
  "version": 1,
  "url": "https://myco.atlassian.net/wiki/spaces/ENG/pages/300000001/Q2+Architecture+Decision%3A+PostgreSQL",
  "created": "2026-03-11T09:00:00.000Z",
  "updated": "2026-03-11T09:00:00.000Z",
  "author": "Remington Bot"
}
```

---

## `trinity confluence update <page-id>`

Update an existing page's title and/or body. The current version is fetched automatically and incremented — no manual version tracking required.

```bash
trinity confluence update 300000001 --title "Q2 Architecture Decision: PostgreSQL (Approved)"
trinity confluence update 300000001 --body "<h2>Decision</h2><p>Approved by architecture board on 2026-03-11.</p>"
trinity confluence update 300000001 --body-file updated_content.html --comment "Added board approval section"
```

**Options:**

| Flag | Description |
|------|-------------|
| `--title TEXT` | New page title |
| `--body TEXT` | New body in HTML storage format |
| `--body-file PATH` | Read new body from a file |
| `--comment TEXT` | Version comment (visible in page history) |

At least one of `--title`, `--body`, or `--body-file` is required.

**JSON response:**

```json
{
  "id": "300000001",
  "title": "Q2 Architecture Decision: PostgreSQL (Approved)",
  "status": "current",
  "space_key": "ENG",
  "space_name": "Engineering",
  "version": 2,
  "url": "https://myco.atlassian.net/wiki/spaces/ENG/pages/300000001",
  "updated": "2026-03-11T10:30:00.000Z",
  "author": "Remington Bot"
}
```

---

## `trinity confluence comment <page-id> <text>`

Add a footer comment to a Confluence page.

```bash
trinity confluence comment 123456789 "Reviewed and confirmed accurate as of 2026-03-11."
```

**JSON response:**

```json
{
  "id": "401000001",
  "page_id": "123456789",
  "author": "Remington Bot",
  "body": "Reviewed and confirmed accurate as of 2026-03-11.",
  "created": "2026-03-11T09:05:00.000Z"
}
```

---

## HTML Storage Format

Confluence stores page content as an HTML subset called "storage format". Common elements:

```html
<!-- Headings -->
<h2>Section Title</h2>

<!-- Paragraphs -->
<p>Plain paragraph text.</p>

<!-- Lists -->
<ul>
  <li>Bullet point one</li>
  <li>Bullet point two</li>
</ul>

<ol>
  <li>Step one</li>
  <li>Step two</li>
</ol>

<!-- Code block (Confluence macro) -->
<ac:structured-macro ac:name="code">
  <ac:parameter ac:name="language">python</ac:parameter>
  <ac:plain-text-body><![CDATA[
def hello():
    print("hello world")
  ]]></ac:plain-text-body>
</ac:structured-macro>

<!-- Info panel -->
<ac:structured-macro ac:name="info">
  <ac:rich-text-body><p>This is an info panel.</p></ac:rich-text-body>
</ac:structured-macro>

<!-- Table -->
<table>
  <tbody>
    <tr>
      <th>Column A</th>
      <th>Column B</th>
    </tr>
    <tr>
      <td>Value 1</td>
      <td>Value 2</td>
    </tr>
  </tbody>
</table>
```

To get a page's current body in storage format (useful for building an update payload):

```bash
trinity --json confluence get 123456789 | jq -r '.body'
```
