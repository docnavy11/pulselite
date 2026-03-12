# Crawl Character Limits & Path Filters

**Date:** 2026-03-12
**Status:** Approved

## Overview

Replace the current page-count cap on crawling with a character-based budget tied to each workspace's billing plan. Add include/exclude path filters to crawl requests. Raise the BFS depth limit from 3 to 10 (not user-configurable).

This mirrors the approach used by Chatbase: customers understand "how much text am I allowed to store" more easily than "how many pages can I crawl".

---

## Section 1: Data Model

### New columns

**`workspaces` table:**
```sql
chars_indexed  BIGINT NOT NULL DEFAULT 0
```
Tracks the total characters currently indexed across all knowledge bases in the workspace. Incremented atomically when a document is ingested; decremented when a document is deleted.

**`documents` table:**
```sql
char_count  INT NOT NULL DEFAULT 0
```
Stores the character count of the document's plain-text extractor output (the string produced by the extractor before chunking — HTML tags stripped, boilerplate removed). Set during ingestion; used to decrement `chars_indexed` on deletion. This is the value `:n` used in the atomic budget check.

### Plan limits

Defined as a Python constant in `backend/app/config.py`:

```python
PLAN_CHAR_LIMITS: dict[str, int | None] = {
    "free":       500_000,
    "starter":  2_000_000,
    "growth":  10_000_000,
    "enterprise": None,    # unlimited
}
```

`None` means no limit enforced. The limit is looked up at ingest time via `workspace.plan` (the field on the `Workspace` model).

### Migrations required

1. `ALTER TABLE workspaces ADD COLUMN chars_indexed BIGINT NOT NULL DEFAULT 0`
2. `ALTER TABLE documents ADD COLUMN char_count INT NOT NULL DEFAULT 0`
3. `ALTER TABLE crawl_jobs DROP COLUMN max_pages`
4. `ALTER TABLE crawl_jobs DROP COLUMN over_limit`
5. `ALTER TABLE crawl_jobs ADD COLUMN include_paths JSONB NOT NULL DEFAULT '[]'`
6. `ALTER TABLE crawl_jobs ADD COLUMN exclude_paths JSONB NOT NULL DEFAULT '[]'`
7. Backfill: for every existing indexed document, compute `char_count` as `SUM(LENGTH(content)) FROM chunks WHERE document_id = <doc_id>`. Chunks do not overlap, so this approximates the extractor output length. Then set `workspaces.chars_indexed = SUM(char_count)` across all indexed documents per workspace.

Note: `pages_discovered` stays on `crawl_jobs` — it remains useful for showing "N pages found during crawl".

---

## Section 2: Crawl Pipeline

### BFS depth

Change `_discover_via_bfs`'s default parameter from `max_depth: int = 3` to `max_depth: int = 10`. `discover_urls` calls `_discover_via_bfs` without passing `max_depth`, so it will use the new default of 10. No user-facing parameter.

### Path filtering

Add a helper function `_matches_paths(url: str, include_paths: list[str], exclude_paths: list[str]) -> bool`:

```python
def _matches_paths(url: str, include_paths: list[str], exclude_paths: list[str]) -> bool:
    path = urlparse(url).path
    if include_paths and not any(path.startswith(p) for p in include_paths):
        return False
    if any(path.startswith(p) for p in exclude_paths):
        return False
    return True
```

Called inside both `_discover_via_bfs` and `_discover_via_sitemap` — any URL that does not pass the filter is silently skipped.

Both private functions must be updated:
- `_discover_via_sitemap(root_url, include_paths, exclude_paths)` — apply `_matches_paths` before appending to `urls`.
- `_discover_via_bfs(root_url, max_depth=10, include_paths=None, exclude_paths=None)` — apply `_matches_paths` before enqueuing or appending discovered URLs.

`discover_urls` passes through the `include_paths`/`exclude_paths` values it receives to both helpers.

`discover_urls` signature change:
```python
# Before
async def discover_urls(root_url: str, max_pages: int) -> CrawlResult

# After
async def discover_urls(
    root_url: str,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
) -> list[str]
```

Use `None` defaults (not `[]`) to avoid the mutable-default footgun; normalise to `[]` at the top of the function body.

`max_pages` is removed entirely. `CrawlResult` dataclass is retired — `discover_urls` returns a plain `list[str]`. The `over_limit` DB column on `CrawlJob` is dropped (migration item 4); `pages_discovered` stays. In `execute_crawl`, the lines `job.pages_discovered = crawl_result.total_discovered` and `job.over_limit = crawl_result.over_limit` are replaced with `job.pages_discovered = len(urls)`. The BFS terminates only when the queue is exhausted (subject to depth=10).

### Character budget enforcement (ingest worker)

The budget check lives in `_run()` in `backend/app/workers/tasks/ingest_document.py`, before the call to `run_ingestion()`. Load the `Document` row, perform the check, then either proceed or mark as skipped — all in one session. The `run_ingestion` call is skipped entirely for budget-exceeded documents.

**Idempotency guard first** — check `document.status in ("indexed", "skipped")`. If true, the document was already processed; return immediately without re-deducting. This is the authoritative guard: it correctly handles zero-char documents (status="indexed", char_count=0) and avoids re-deduction for documents that committed the workspace budget update but failed before their status was set to "indexed" — those will be re-processed by the retry, which is the correct behaviour since the partial commit is rolled back by the outer exception handler.

Then perform the atomic budget check in a single transaction with the document update:

```sql
UPDATE workspaces
SET    chars_indexed = chars_indexed + :n
WHERE  id = :workspace_id
  AND  (:limit IS NULL OR chars_indexed + :n <= :limit)
RETURNING chars_indexed
```

- If the `UPDATE` returns a row → budget accepted. Set `document.char_count = n`, commit both changes in the same transaction.
- If the `UPDATE` returns no rows (limit would be exceeded) → set `document.status = "skipped"`, set `document.char_count = 0`, commit. Do **not** store the extracted text or embeddings.

Because `document.char_count` is set in the same transaction as the workspace deduction, a task retry will hit the idempotency guard and skip the deduction, preventing double-counting.

`"skipped"` is a new value for the `document.status` enum/column.

### Decrement on delete

When a document is deleted (hard delete), decrement `workspaces.chars_indexed` by the document's `char_count`:

```sql
UPDATE workspaces
SET chars_indexed = GREATEST(0, chars_indexed - :char_count)
WHERE id = :workspace_id
```

---

## Section 3: API

### `CrawlRequest` schema changes

**Remove:** `max_pages: int`
**Add:**
```python
include_paths: list[str] = Field(default_factory=list,
    description="URL path prefixes to include, e.g. ['/blog', '/docs']. Empty = all paths.")
exclude_paths: list[str] = Field(default_factory=list,
    description="URL path prefixes to exclude, e.g. ['/admin', '/private'].")
```

Add a `field_validator` for both fields: entries must be non-empty strings that start with `/`; list length capped at 20. An empty string in `include_paths` would match every URL (defeating the filter), so it must be rejected.

### `prepare_crawl` / `CrawlStartResult` signature changes

`prepare_crawl` replaces `max_pages: int` with `include_paths: list[str]` and `exclude_paths: list[str]`, which it stores directly on the `CrawlJob` row.

`CrawlStartResult` drops the `over_limit: bool` and `limit: int` fields; the API response replaces them with `chars_remaining: int | None` sourced from `GET /usage`.

The legacy `start_crawl()` wrapper function in `crawl_service.py` (which duplicates `prepare_crawl` + Celery dispatch) is deleted; callers should use `prepare_crawl` + direct `crawl_website.delay()`.

### Response changes

In `CrawlResponse` (initial `POST /crawl` response):
- Remove: `over_limit: bool`, `limit: int`
- Do **not** add `docs_skipped` — no documents exist yet when this response is sent.

In `CrawlJobStatusResponse` (polled status) and `CrawlJobSummary` (job list):
- Remove: `over_limit: bool`, `limit: int`
- Add: `docs_skipped: int` (count of documents with `status="skipped"` for this crawl job)

`docs_skipped` lets the frontend show the "some pages were skipped" warning without a separate document-listing call.

`CrawlJobSummary` (the schema used for the jobs list) also adds `docs_skipped: int = 0` so historical crawls can show the warning in list views.

### New endpoint

```
GET /api/v1/workspaces/{workspace_id}/usage
```

Response:
```json
{
  "chars_indexed": 1234567,
  "chars_limit": 2000000,
  "chars_remaining": 765433,
  "plan": "starter"
}
```

`chars_limit` and `chars_remaining` are `null` for enterprise (unlimited). `chars_remaining` is computed server-side as `max(0, chars_limit - chars_indexed)` to avoid negative values if a workspace was grandfathered above its limit. This endpoint is used by the frontend billing/settings page.

### Document status

The document status enum gains the value `"skipped"`. Existing statuses: `pending`, `processing`, `indexed`, `failed`. New: `skipped` (budget exceeded at ingest time).

---

## Section 4: Frontend

### Crawl form

Replace the `max_pages` number input with two text fields:

- **Include paths** — placeholder `/blog, /docs`
- **Exclude paths** — placeholder `/admin, /private`

Each field accepts a comma-separated list. On submit, split on commas, trim whitespace, and send as `include_paths`/`exclude_paths` arrays.

Both fields are optional (empty = no filter).

### Character usage bar

On the billing/settings page, add a usage bar:

```
Characters indexed: 1,234,567 / 2,000,000  (62%)
[████████████░░░░░░░░] 765,433 remaining
```

- Bar color: green below 80%, amber 80–95%, red above 95%.
- Source: `GET /workspaces/{id}/usage`.
- For enterprise plan: show `1,234,567 indexed (unlimited plan)`, no bar.

### `CrawlStatusPanel`

Where "pages indexed" or "limit" was shown, show characters instead:

- During crawl: `Chars indexed: 45,231` — sourced from `GET /usage` (workspace total), polled at the same interval as the existing job-status poll.
- After crawl: `Total chars: 45,231` — same source, final value.
- If `docs_skipped > 0` in the job-status response: show a warning banner — "Some pages were skipped because the character limit was reached."

Note: per-job character counts are not tracked separately; the panel shows the workspace total, which is sufficient because a workspace typically runs one crawl at a time.

---

## Files to Modify

| File | Change |
|------|--------|
| `backend/alembic/versions/` | New migration: add `chars_indexed` to workspaces, `char_count` to documents; drop `max_pages`/`over_limit` from crawl_jobs; add `include_paths`/`exclude_paths` JSONB to crawl_jobs; backfill `char_count` from chunks; backfill `chars_indexed` on workspaces |
| `backend/app/config.py` | Add `PLAN_CHAR_LIMITS` constant |
| `backend/app/models/workspace.py` | Add `chars_indexed: Mapped[int]` column |
| `backend/app/models/document.py` | Add `char_count: Mapped[int]` column; add `"skipped"` to status enum |
| `backend/app/models/knowledge.py` | Drop `max_pages`/`over_limit` from `CrawlJob`; add `include_paths`/`exclude_paths` (JSON-typed) columns |
| `backend/app/services/crawler.py` | Raise depth 3→10; add `_matches_paths`; update `_discover_via_sitemap` signature; retire `CrawlResult` dataclass; `discover_urls` returns `list[str]` |
| `backend/app/services/crawl_service.py` | `prepare_crawl` replaces `max_pages` with `include_paths`/`exclude_paths`; `execute_crawl` reads them from `CrawlJob`, passes to `discover_urls`, sets `pages_discovered = len(urls)`; delete `start_crawl` legacy wrapper; drop `CrawlStartResult.over_limit`/`limit` |
| `backend/app/workers/tasks/ingest_document.py` | Add idempotency guard and atomic char budget check in `_run()` before `run_ingestion()`; set `status="skipped"` when over budget |
| `backend/app/services/document_service.py` | Decrement `chars_indexed` on document delete |
| `backend/app/schemas/crawl.py` | Drop `max_pages`; add `include_paths`/`exclude_paths` with field_validator; drop `over_limit`/`limit` from `CrawlResponse`, `CrawlJobStatusResponse`, `CrawlJobSummary`; add `docs_skipped: int` to `CrawlJobStatusResponse` and `CrawlJobSummary` only; add `WorkspaceUsageResponse` |
| `backend/app/api/v1/workspaces.py` | Add `GET /usage` endpoint |
| `frontend/src/lib/api-functions.ts` | Add `getWorkspaceUsage()`; update `startCrawl()` payload |
| `frontend/src/lib/types.ts` | Add `WorkspaceUsage` type; update `CrawlRequest` type |
| `frontend/src/app/(dashboard)/knowledge/[id]/page.tsx` | Replace max_pages field with include/exclude path fields |
| `frontend/src/components/crawl/CrawlStatusPanel.tsx` | Show chars instead of pages; poll `/usage`; show warning when `docs_skipped > 0` |
| `frontend/src/app/(dashboard)/settings/billing/page.tsx` | Add character usage bar |

---

## What Is Not Changing

- No user-exposed depth setting — depth=10 is fixed.
- No per-crawl-job character limit — the limit applies workspace-wide.
- No changes to auth, SSO, or any non-crawl/ingest code paths.
- Embedding model and chunking logic are unchanged.
- PDF and other document types already supported by existing extractors; no changes needed there.

---

## Testing

| Test | Layer |
|------|-------|
| Free plan workspace: ingest stops at 500k chars; subsequent docs have `status="skipped"` | Integration (`tests/integration/`) — real DB, call ingest service directly (not via Celery task) to hit coverage gate |
| Path filter `include_paths=["/blog"]`: only `/blog/*` URLs returned by `discover_urls` | Unit (`tests/unit/`) — call `_matches_paths` and `discover_urls` with a mock HTTP session |
| Path filter `exclude_paths=["/admin"]`: `/admin/*` URLs absent from result | Unit |
| Atomic budget: two concurrent ingest calls for the same workspace do not together exceed the plan limit | Integration — run two concurrent `asyncio.gather` calls against a real DB |
| `GET /usage` returns correct `chars_indexed` and `chars_remaining` after ingestion | Integration |
| Document delete decrements `chars_indexed` | Integration |
| `chars_remaining` is clamped to 0 when `chars_indexed > chars_limit` | Unit — call the usage schema builder directly |
| Retry idempotency: calling ingest twice on the same document only deducts the budget once | Integration |
| Backfill migration: `chars_indexed` equals `SUM(char_count)` across indexed documents after migration runs | Migration test or manual verification |
| Frontend usage bar shows correct percentage and colour thresholds (green/amber/red) | Vitest unit test on the bar component logic |
| Skipped-docs warning appears in `CrawlStatusPanel` when at least one document has `status="skipped"` | Vitest unit test |
