# Logs Page Design Spec

**Date:** 2026-03-12
**Status:** Approved

## Goal

Add a workspace-wide "Logs" page to the dashboard that surfaces all crawl runs and all document ingestion jobs across every chatbot in the workspace.

## Architecture

Two new read-only API endpoints on the backend. One new frontend page at `/logs` with two tabs. No new DB tables or schema migrations — all data already exists in `CrawlJob` and `Document`.

**Tech Stack:** FastAPI (backend), React + React Router + Zustand (frontend), Vitest (tests).

---

## Backend

### New endpoints (added to `backend/app/api/v1/crawl.py`)

#### `GET /workspaces/{workspace_id}/logs/crawl-runs`

Returns all `CrawlJob` rows belonging to the workspace, newest first, with pagination.

Query params: `limit: int = Query(50, ge=1, le=200)`, `offset: int = Query(0, ge=0)`

Response schema `CrawlRunLogItem`:
```
job_id: str
chatbot_id: str | None
chatbot_name: str | None       # joined from Chatbot via KB
root_url: str
status: str                    # pending | running | completed | failed
phase: str | None
pages_discovered: int
pages_queued: int
pages_failed: int
docs_indexed: int              # count of Document rows with status="indexed" for this KB
                               # NOTE: scoped to the KB (not the individual job), so on KBs
                               # with multiple crawl runs all rows show the same total.
                               # Column label in UI: "Indexed (KB total)"
error_message: str | None
created_at: str
started_at: str | None         # None for pending jobs
completed_at: str | None
```

Response wrapper `CrawlRunLogResponse`:
```
items: list[CrawlRunLogItem]
total: int
```

Join: `CrawlJob → KnowledgeBase → Chatbot` (all left-joined, nulls when KB has no chatbot).

#### `GET /workspaces/{workspace_id}/logs/documents`

Returns all `Document` rows belonging to the workspace, newest first, with pagination.

Query params: `limit: int = Query(50, ge=1, le=200)`, `offset: int = Query(0, ge=0)`

Response schema `DocumentLogItem`:
```
id: str
title: str | None
source_url: str | None
source_type: str               # url | text | file
status: str                    # pending | processing | indexed | failed | skipped
chunk_count: int
last_indexed_at: str | None
knowledge_base_id: str
knowledge_base_name: str       # joined from KnowledgeBase
chatbot_id: str | None
chatbot_name: str | None       # joined from Chatbot via KB
```

Response wrapper `DocumentLogResponse`:
```
items: list[DocumentLogItem]
total: int
```

Join: `Document → KnowledgeBase → Chatbot` (left-joined).

---

## Frontend

### Route
`/logs` — added to React Router in `frontend/src/App.tsx` as a child of the `DashboardLayout` route block:
```tsx
import LogsPage from "./app/(dashboard)/logs/page";
// inside the DashboardLayout <Route>:
<Route path="/logs" element={<LogsPage />} />
```

### Sidebar
New entry in `MAIN_NAV` in `Sidebar.tsx`:
```
{ href: "/logs", label: "Logs", Icon: IconLogs }
```
Icon: Add `IconLogs` as a new SVG component in `frontend/src/components/icons/NavIcons.tsx`, following the existing `IconProps` pattern (a scroll/list SVG). **Do not** use lucide-react here — all sidebar icons are custom SVGs in `NavIcons.tsx`. Inserted after "Conversations".

### Page: `frontend/src/app/(dashboard)/logs/page.tsx`

Two tabs: **Crawl Runs** (default) | **Documents**

Tab state managed with local `useState` — no URL param needed.

#### Crawl Runs tab

Table columns:
| Column | Value |
|---|---|
| Chatbot | `chatbot_name` or "—" |
| URL | `root_url` (truncated, links out) |
| Status | Badge: pending (gray) / running (blue + spinner) / completed (green) / failed (red) |
| Pages | `pages_queued / pages_discovered` (e.g. "12 / 15") |
| Failed | `pages_failed` (shown in red if > 0, else "—") |
| Indexed | `docs_indexed` |
| Error | `error_message` truncated to 60 chars, full text on hover tooltip |
| Started | `started_at` as relative time if non-null, else `created_at` as relative time |
| Duration | computed from `started_at` → `completed_at`, or "—" |

"Load more" button at bottom (increments offset by 50). Shows total count: "Showing N of T runs".

#### Documents tab

Table columns:
| Column | Value |
|---|---|
| Title | `title` or source_url filename, truncated |
| Source | `source_url` truncated, external link icon |
| Type | `source_type` badge: url / text / file |
| Knowledge Base | `knowledge_base_name` |
| Chatbot | `chatbot_name` or "—" |
| Status | Badge: pending (gray) / processing (blue) / indexed (green) / failed (red) / skipped (yellow) |
| Chunks | `chunk_count` |
| Indexed At | relative time or "—" |

"Load more" at bottom. Shows total count.

### API functions (added to `api-functions.ts`)

```ts
getCrawlRunLogs(workspaceId, limit, offset): Promise<CrawlRunLogResponse>
getDocumentLogs(workspaceId, limit, offset): Promise<DocumentLogResponse>
```

### Types (added to `types.ts`)

```ts
interface CrawlRunLogItem { ... }
interface CrawlRunLogResponse { items: CrawlRunLogItem[]; total: number; }
interface DocumentLogItem { ... }
interface DocumentLogResponse { items: DocumentLogItem[]; total: number; }
```

---

## Error handling

- Both endpoints return `[]` / `total: 0` on empty — no special error state needed.
- Network errors show a generic "Failed to load" inline message with a retry button.
- Running jobs auto-refresh every 5 seconds while the Crawl Runs tab is active. The interval **and** any in-flight fetch must be cancelled via `AbortController` on tab switch and on component unmount to prevent stale state updates.

---

## Testing

### Backend
- `tests/unit/test_logs_endpoints.py`: test workspace isolation (workspace A cannot see workspace B's jobs/docs), empty workspace returns `{items: [], total: 0}`, pagination `limit`/`offset` respected (correct subset returned, correct `total`), `offset` beyond `total` returns `items: []` with correct `total`, chatbot name join works when KB has no chatbot (null).

### Frontend
- `src/test/logs-page.test.ts`: MSW handlers mock both endpoints; verify crawl runs tab renders correct row count; verify documents tab renders; verify "load more" increments offset; verify relative time rendering.

---

## Out of scope

- Filtering by status, chatbot, or date range (future)
- Real-time streaming updates (polling every 5s for running jobs is sufficient)
- Deleting or re-running jobs from this page
