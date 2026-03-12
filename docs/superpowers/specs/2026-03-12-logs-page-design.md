# Logs Page Design Spec

**Date:** 2026-03-12
**Status:** Approved

## Goal

Add a workspace-wide "Logs" page to the dashboard that surfaces all crawl runs and all document ingestion jobs across every chatbot in the workspace — with full step-level detail for the ingestion pipeline so errors are visible and actionable.

## Architecture

- Two new columns on `Document` (`error_message`, `ingestion_steps`) captured during pipeline execution
- One Alembic migration
- New `backend/app/api/v1/logs.py` router with two workspace-scoped endpoints, registered in `main.py`
- One new frontend page at `/logs` with two tabs; Documents tab rows expand to show the step timeline

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, React + React Router + Zustand, Vitest.

---

## Backend

### 1. Model change — `backend/app/models/knowledge.py`

Add two columns to `Document`:

```python
error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
ingestion_steps: Mapped[list | None] = mapped_column(JSONB, nullable=True)
```

Import: `from sqlalchemy.dialects.postgresql import JSONB` (already used elsewhere in the models file).

`ingestion_steps` stores a list of step dicts (see step schema below). `error_message` stores the top-level failure reason.

### 2. Migration — `backend/alembic/versions/<timestamp>_document_ingestion_logging.py`

```python
from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("ingestion_steps", postgresql.JSONB(), nullable=True))
```

### 3. Pipeline instrumentation — `backend/app/services/ingestion/pipeline.py`

**Step record shape:**

```python
{
  "step": str,          # see step names below
  "status": str,        # "ok" | "failed" | "skipped"
  "started_at": str,    # ISO 8601 UTC timestamp
  "duration_ms": int,
  "detail": str | None, # human-readable outcome summary
  "error": str | None,  # exception message on failure, None on success
}
```

**Step names by source type:**

Standard path (url / file / text — handled by `_extract()` + shared chunk/embed/index):
- `extract` — `_extract(document)` call
- `budget_check` — character limit enforcement
- `chunk` — `_chunk(document, content)`
- `embed` — `embed_chunks(texts)`
- `index` — `delete_by_document` + `insert_chunks`

Notion, Google Drive, Dropbox (inline extract in their own branches, but share chunk/embed/index):
- `extract` — their fetch call (Notion API, Drive API, Dropbox API)
- `chunk` — `_chunk(document, content)`
- `embed` — `embed_chunks(texts)`
- `index` — `delete_by_document` + `insert_chunks`
- (no `budget_check` — these branches do not have the character budget gate)

Fan-out (sitemap, salesforce, zendesk):
- `extract_sources` — the extractor call that yields URLs/articles
- `fan_out` — creating and queuing child `Document` rows

**`detail` values:**

| Step | On success | On skip | On failure |
|---|---|---|---|
| `extract` | `"{N} chars extracted"` | — | `str(exc)` |
| `budget_check` | `"{N} chars accepted ({remaining} remaining)"` | `"over limit — document skipped"` | — |
| `chunk` | `"{N} chunks produced"` | `"no chunks (empty content)"` | `str(exc)` |
| `embed` | `"{N} embeddings generated"` | — | `str(exc)` |
| `index` | `"{N} vectors stored"` | — | `str(exc)` |
| `extract_sources` | `"{N} sources discovered"` | — | `str(exc)` |
| `fan_out` | `"{N} child documents queued"` | — | `str(exc)` |

**Helper pattern (defined inside `run_ingestion`):**

```python
steps: list[dict] = []

def _record(step: str, status: str, t0: datetime, detail: str | None = None, error: str | None = None) -> None:
    steps.append({
        "step": step,
        "status": status,
        "started_at": t0.isoformat(),
        "duration_ms": int((datetime.now(timezone.utc) - t0).total_seconds() * 1000),
        "detail": detail,
        "error": error,
    })
```

**Failure commit pattern (critical):**

The Celery task (`_run`) rolls back the session on exception, which would discard any `document.ingestion_steps` written to the in-memory object. To survive the rollback, the pipeline must commit failure state **before re-raising**:

```python
# Inside each per-step except block:
except Exception as exc:
    _record("extract", "failed", t0, error=str(exc))
    document.status = "failed"
    document.error_message = str(exc)
    document.ingestion_steps = steps
    await db.commit()   # commit before raising — survives the task's session.rollback()
    raise
```

The same pattern applies in every branch (notion, gdrive, dropbox, sitemap, salesforce, zendesk). Always write `document.ingestion_steps = steps` and `await db.commit()` before re-raising any exception inside `run_ingestion`.

On success, at the very end of the function, before returning:
```python
document.ingestion_steps = steps
# (caller commits via session.commit() in _run)
```

**Scope note:** `notion`, `google_drive`, and `dropbox` branches inline their own chunk/embed/index logic (they do not call the shared `_extract()` path). Step recording must be added inline within each of those branches, following the same pattern. The `budget_check` step is **not** applicable to those three types (they have no character budget gate in the current code).

### 4. Task — `backend/app/workers/tasks/ingest_document.py`

`_mark_document_failed` opens a fresh session and can only write fields it knows about. Add `error_message`:

```python
async def _mark_document_failed(document_id: uuid.UUID, reason: str) -> None:
    ...
    if doc and doc.status not in ("indexed", "skipped", "failed"):
        doc.status = "failed"
        doc.error_message = reason   # ADD THIS
        await session.commit()
```

This handles the "max retries exceeded" and unexpected top-level exception cases. The pipeline itself handles writing `ingestion_steps` for in-pipeline failures (see section 3).

### 5. Schemas

**`backend/app/schemas/documents.py`** — add to `DocumentResponse`:
```python
error_message: Optional[str] = None
ingestion_steps: Optional[list] = None
```

**`backend/app/schemas/logs.py`** (new file):
```python
from typing import Optional
from pydantic import BaseModel

class CrawlRunLogItem(BaseModel):
    job_id: str
    chatbot_id: Optional[str] = None
    chatbot_name: Optional[str] = None
    root_url: str
    status: str
    phase: Optional[str] = None
    pages_discovered: int
    pages_queued: int
    pages_failed: int
    docs_indexed: int        # count of indexed docs in KB — KB-total, not per-job
                             # (matches existing list_crawl_history behaviour)
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None   # None for pending jobs
    completed_at: Optional[str] = None

class CrawlRunLogResponse(BaseModel):
    items: list[CrawlRunLogItem]
    total: int

class DocumentLogItem(BaseModel):
    id: str
    title: Optional[str] = None
    source_url: Optional[str] = None
    source_type: str
    status: str
    chunk_count: int
    last_indexed_at: Optional[str] = None
    error_message: Optional[str] = None
    ingestion_steps: Optional[list] = None
    knowledge_base_id: str
    knowledge_base_name: str
    chatbot_id: Optional[str] = None
    chatbot_name: Optional[str] = None

class DocumentLogResponse(BaseModel):
    items: list[DocumentLogItem]
    total: int
```

### 6. API router — `backend/app/api/v1/logs.py` (new file)

Register in `backend/app/main.py` with `prefix=""` (workspace prefix lives in the router).

```python
router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["logs"])
```

#### `GET /workspaces/{workspace_id}/logs/crawl-runs`

Query params: `limit: int = Query(50, ge=1, le=200)`, `offset: int = Query(0, ge=0)`

- Count all `CrawlJob` rows where `workspace_id == workspace.id` → `total`
- Fetch paginated rows newest-first (`created_at DESC`), left-join `KnowledgeBase` → `Chatbot`
- Compute `docs_indexed` per KB in a single aggregate subquery (same approach as existing `list_crawl_history`)
- Return `CrawlRunLogResponse`

#### `GET /workspaces/{workspace_id}/logs/documents`

Query params: `limit: int = Query(50, ge=1, le=200)`, `offset: int = Query(0, ge=0)`

- Count all `Document` rows where `workspace_id == workspace.id` → `total`
- Fetch paginated rows ordered by `created_at DESC` (most recently created first — gives pending/failed documents near the top while they are being processed; `last_indexed_at` is null for those)
- Left-join `KnowledgeBase` → `Chatbot`
- Return `DocumentLogResponse`

---

## Frontend

### Route — `frontend/src/App.tsx`

```tsx
import LogsPage from "./app/(dashboard)/logs/page";
// inside DashboardLayout <Route> block:
<Route path="/logs" element={<LogsPage />} />
```

### Sidebar icon — `frontend/src/components/icons/NavIcons.tsx`

Add `IconLogs` as a custom SVG (three horizontal lines with a small circle on the left — "list" motif), following the existing `IconProps` pattern (`className`, `size` props). Do **not** use lucide-react — all sidebar icons are custom SVGs in this file.

### Sidebar entry — `frontend/src/components/layout/Sidebar.tsx`

```ts
{ href: "/logs", label: "Logs", Icon: IconLogs }
```
Insert after "Conversations" in `MAIN_NAV`. The existing `startsWith` active-highlight logic handles `/logs` correctly with no changes.

### Types — `frontend/src/lib/types.ts`

```ts
export interface IngestionStep {
  step: string;
  status: "ok" | "failed" | "skipped";
  started_at: string;
  duration_ms: number;
  detail: string | null;
  error: string | null;
}

export interface CrawlRunLogItem {
  job_id: string;
  chatbot_id: string | null;
  chatbot_name: string | null;
  root_url: string;
  status: string;
  phase: string | null;
  pages_discovered: number;
  pages_queued: number;
  pages_failed: number;
  docs_indexed: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}
export interface CrawlRunLogResponse { items: CrawlRunLogItem[]; total: number; }

export interface DocumentLogItem {
  id: string;
  title: string | null;
  source_url: string | null;
  source_type: string;
  status: string;
  chunk_count: number;
  last_indexed_at: string | null;
  error_message: string | null;
  ingestion_steps: IngestionStep[] | null;
  knowledge_base_id: string;
  knowledge_base_name: string;
  chatbot_id: string | null;
  chatbot_name: string | null;
}
export interface DocumentLogResponse { items: DocumentLogItem[]; total: number; }
```

### API functions — `frontend/src/lib/api-functions.ts`

```ts
getCrawlRunLogs(workspaceId: string, limit: number, offset: number): Promise<CrawlRunLogResponse>
getDocumentLogs(workspaceId: string, limit: number, offset: number): Promise<DocumentLogResponse>
```

### Page — `frontend/src/app/(dashboard)/logs/page.tsx`

Two tabs: **Crawl Runs** (default) | **Documents**

Tab state: `useState<"crawl" | "documents">("crawl")`

#### Crawl Runs tab

Table columns:

| Column | Value |
|---|---|
| Chatbot | `chatbot_name` or "—" |
| URL | `root_url` truncated, opens in new tab |
| Status | Badge: pending (gray) / running (blue + spinner) / completed (green) / failed (red) |
| Pages | `pages_queued / pages_discovered` |
| Failed pages | `pages_failed` in red if > 0, else "—" |
| Indexed (KB total) | `docs_indexed` |
| Error | `error_message` truncated 60 chars, full text on hover tooltip |
| Started | `started_at` relative time if non-null, else `created_at` relative time |
| Duration | `completed_at − started_at` formatted as `Xm Ys`, or "—" |

**Auto-refresh:** Poll every 5 s while this tab is active **and** at least one row has `status === "running"` or `status === "pending"`. After each successful response, re-evaluate whether polling should continue; stop the interval when no rows are active. Use `setInterval` + `AbortController` — cancel both the interval and any in-flight fetch on tab switch and on unmount.

"Load more" button (increments offset by 50). "Showing N of T runs."

#### Documents tab

Table rows are **expandable** — clicking a row toggles an inline step timeline below it.

Table columns:

| Column | Value |
|---|---|
| Title | `title` or URL basename, truncated |
| Source | `source_url` truncated, external link icon |
| Type | Badge: url / text / file / notion / google_drive / dropbox / salesforce / zendesk / sitemap |
| Knowledge Base | `knowledge_base_name` |
| Chatbot | `chatbot_name` or "—" |
| Status | Badge: pending (gray) / processing (blue) / indexed (green) / failed (red) / skipped (yellow) |
| Chunks | `chunk_count` |
| Indexed At | `last_indexed_at` as relative time, or "—" |

**Expanded step timeline** (rendered inline below the row when expanded):

Renders `ingestion_steps` as a vertical list of `StepRow` items (same visual language as the wizard's `PhaseRow`):
- Green check circle: `status === "ok"`
- Red triangle: `status === "failed"`
- Yellow dash circle: `status === "skipped"`
- Each row shows: human-readable step label, `detail` text, duration (`Xms`), and `error` message in red if present

Step label mapping:
```
extract          → "Extract content"
budget_check     → "Character budget"
chunk            → "Chunk text"
embed            → "Generate embeddings"
index            → "Store vectors"
extract_sources  → "Discover sources"
fan_out          → "Queue child documents"
```

If `ingestion_steps` is `null` (document pre-dates this feature): show "No step data recorded for this document."

If `status === "failed"` and `error_message` is non-null: show a red error banner above the steps list.

"Load more" at bottom. "Showing N of T documents."

---

## Error handling

- Both endpoints return `{items: [], total: 0}` on empty — no special UI state needed.
- Network errors: inline "Failed to load" with a Retry button.
- Auto-refresh (crawl tab): `AbortController` cancels in-flight requests on tab switch and unmount; interval stops automatically when no rows are `pending` or `running`.

---

## Testing

### Backend — `tests/unit/test_logs_endpoints.py`

- Workspace isolation: workspace A cannot see workspace B's jobs or documents
- Empty workspace: both endpoints return `{items: [], total: 0}`
- Pagination `limit`/`offset`: correct subset returned, correct `total` in all cases
- `offset` beyond `total`: returns `{items: [], total: N}` (total unchanged)
- `chatbot_name` is `None` when KB has no chatbot
- `docs_indexed` reflects correct count of indexed documents for the KB

### Backend — `tests/unit/test_ingestion_pipeline.py` (additions)

- Success path: `ingestion_steps` contains all expected step names with `status: "ok"`
- Extract failure: `ingestion_steps[0]` has `status: "failed"` and `error` containing the exception message; `document.error_message` is set
- Budget exceeded: `budget_check` step has `status: "skipped"`; document `status` is `"skipped"`
- Failure commit survives rollback: after a pipeline failure, the document read from a **new session** (simulating the post-rollback state) still has `ingestion_steps` and `error_message` set — verifies that the pre-raise commit in the pipeline is not lost
- Retry idempotency: a document already in `status: "indexed"` is skipped without overwriting `ingestion_steps`

### Frontend — `src/test/logs-page.test.ts`

- Crawl runs tab: MSW mock returns 3 jobs; all 3 rows render with correct status badges
- Documents tab: renders rows; clicking a row expands the step timeline
- `StepRow` icons: `ok` → green check, `failed` → red triangle, `skipped` → yellow dash
- "Load more" triggers a second fetch with `offset=50`
- `ingestion_steps: null` in expanded row shows fallback "No step data" message
- `error_message` non-null with `status: "failed"` shows red banner in expanded row

---

## Out of scope

- Filtering by status, chatbot, or date range (future)
- Real-time streaming of step updates mid-ingestion
- Deleting or re-running jobs from this page
- Retroactive backfill of `ingestion_steps` for existing documents
