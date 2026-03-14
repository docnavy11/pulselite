# Activity Console — Design Spec

## Goal

Add a floating, app-wide activity console that shows real-time updates from all Celery background tasks via Socket.IO. Users can monitor crawls, ingestion, analysis, clustering, exports, and other background work from any page.

## Context

The app has 13 Celery task files (some containing multiple tasks, e.g. `generate_qa.py` has 3). 8 tasks already emit domain-specific Socket.IO events (`crawl:progress`, `document:status_changed`, `chatbot:status_changed`, `workspace:usage_updated`, `qa:questions_generated`, `qa:pair_updated`). The remaining 8 are silent:

| Task | File |
|------|------|
| `analyze_conversation` | `workers/tasks/analyze_conversation.py` |
| `compute_sentiment_trends` | `workers/tasks/compute_sentiment_trends.py` |
| `cluster_gaps` | `workers/tasks/cluster_gaps.py` |
| `send_weekly_digest_task` | `workers/tasks/weekly_digest.py` |
| `export_workspace_data` | `workers/tasks/gdpr_export.py` |
| `sync_stale_documents` | `workers/tasks/sync_documents.py` |
| `trigger_auto_recharge` | `workers/tasks/auto_recharge.py` |
| `purge_old_data` | `workers/tasks/purge_old_data.py` |

Existing domain events stay unchanged. Page-specific subscribers (`CrawlStatusPanel`, `SourcesTab`, `setup/page`, `qa/page`) continue working as before.

## Architecture

### Approach: Unified generic `task:*` events

Three generic Socket.IO events with a standard payload shape. The floating console subscribes to these plus existing completion/error events for full visibility.

Existing domain-specific events are not modified or replaced.

---

## Backend

### Generic task event helper

Add `emit_task_event()` to `backend/app/services/realtime.py`:

```python
async def emit_task_event(
    workspace_id: str | uuid.UUID,
    event_type: str,          # "started" | "progress" | "completed"
    task_name: str,
    task_id: str,
    detail: str | None = None,
    current: int | None = None,
    total: int | None = None,
    error: str | None = None,
) -> None:
    await emit_to_workspace(
        str(workspace_id),
        f"task:{event_type}",
        {
            "task_name": task_name,
            "task_id": task_id,
            "detail": detail,
            "current": current,
            "total": total,
            "error": error,
        },
    )
```

### Celery integration note

`emit_task_event` is `async`. All `await emit_task_event(...)` calls **must** be placed inside the `async def _run(...)` / `async def _compute()` / `async def _cluster()` inner function — never in the synchronous `@celery_app.task` wrapper. The existing `emit_to_workspace` creates a fresh Redis manager per call (lazy `_create_manager()` pattern), so no stale event loop issues arise inside these async helpers.

### Task ID sourcing

For tasks declared with `bind=True`, use `self.request.id` as `task_id`. For tasks without `bind=True` (`cluster_gaps`, `compute_sentiment_trends`, `purge_old_data`, `send_weekly_digest_task`, `sync_stale_documents`), add `bind=True` to the decorator and use `self.request.id`.

### Events

| Event | Payload | When |
|-------|---------|------|
| `task:started` | `{ task_name, task_id, detail? }` | Task begins work |
| `task:progress` | `{ task_name, task_id, current, total, detail? }` | Per-item progress |
| `task:completed` | `{ task_name, task_id, detail?, error? }` | Task finished — if `error` is non-null, treat as failure; otherwise success |

### Skip behavior

Tasks that detect early-exit conditions (idempotency checks like `analyze_conversation` finding an existing analysis, or `trigger_auto_recharge` finding sufficient balance or auto-recharge disabled) should **not** emit `task:started`. They exit silently. This prevents noisy "started → completed" pairs for no-ops. The skip rule applies to: `analyze_conversation` (already analyzed), `trigger_auto_recharge` (disabled or balance sufficient).

### Per-task emissions

| Celery Task | `task_name` | Events emitted |
|-------------|-------------|----------------|
| `analyze_conversation` | `analyze_conversation` | `started` + `completed` (skip both if already analyzed) |
| `compute_sentiment_trends` | `compute_sentiment` | Per-workspace: `started` + `completed` |
| `cluster_gaps` | `cluster_gaps` | Per-workspace: `started` + `completed` (with cluster count in detail). Emit calls go in `_cluster()`'s for-loop wrapping `_cluster_workspace()`, not inside `_cluster_workspace()` itself. |
| `send_weekly_digest_task` | `weekly_digest` | Per-workspace: `started` + `completed` |
| `export_workspace_data` | `export_data` | `started` + `completed` |
| `sync_stale_documents` | `sync_documents` | Per-workspace: `started` + `completed` (with queued count in detail) |
| `trigger_auto_recharge` | `auto_recharge` | `started` + `completed` (skip both if auto-recharge disabled or balance sufficient) |
| `purge_old_data` | `purge_data` | Per-workspace: `started` + `completed` (with deleted count in detail) |

### Workspace scoping

- **Workspace-scoped tasks** (`analyze_conversation`, `export_workspace_data`, `trigger_auto_recharge`): receive `workspace_id` as argument. Emit directly to that workspace's room.
- **Global tasks that iterate workspaces** (`compute_sentiment_trends`, `cluster_gaps`, `purge_old_data`, `send_weekly_digest_task`): emit `task:started` and `task:completed` per-workspace inside the loop iteration. Each workspace sees only its own activity. There is no global "started" event — the task begins silently and emits per-workspace as it processes each one. The same `self.request.id` is used as `task_id` across all workspace iterations — this is fine because each workspace room only sees its own events.
- **`sync_stale_documents`**: iterates documents, not workspaces. After querying stale documents, group them by `doc.workspace_id` using a dict, then emit per-workspace `task:started` (with `detail: "Syncing N documents"`) before dispatching and `task:completed` after. Example restructure:
  ```python
  from collections import defaultdict
  by_ws: dict[str, list[str]] = defaultdict(list)
  for doc in documents:
      by_ws[str(doc.workspace_id)].append(str(doc.id))
  for ws_id, doc_ids in by_ws.items():
      await emit_task_event(ws_id, "started", "sync_documents", task_id, detail=f"Syncing {len(doc_ids)} documents")
      # ... dispatch ingest_document.delay() for each doc_id ...
      await emit_task_event(ws_id, "completed", "sync_documents", task_id, detail=f"Queued {len(doc_ids)} documents")
  ```

### Bulk trigger ("Analyze all")

The API endpoint (`POST .../intelligence/trigger/analyze-all`) emits a single `task:started` with `task_name: "analyze_all"` and `detail: "Queued N conversations"`, followed by a `task:completed` immediately (the endpoint's own work is done — it just dispatched). Since this runs in the FastAPI route handler (not a Celery task), generate a `task_id` with `str(uuid.uuid4())` — there is no `self.request.id` available. Individual `analyze_conversation` tasks appear as separate entries in the console. No grouping — they are independent entries.

---

## Frontend

### Event types

Add to `frontend/src/lib/types.ts`:

```typescript
export interface TaskEvent {
  task_name: string;
  task_id: string;
  detail?: string | null;
  current?: number | null;
  total?: number | null;
  error?: string | null;
}
```

### Hook: `useActivityConsole`

File: `frontend/src/hooks/useActivityConsole.ts`

Manages a local array of activity entries. Subscribes to:
- `task:started` → add entry with `status: "running"`
- `task:progress` → update existing entry's `current`/`total` (match by `task_id`)
- `task:completed` → if `error` is non-null, set `status: "error"`; otherwise set `status: "done"` (match by `task_id`)
- `crawl:completed` → add entry with `id: data.job_id`, `taskName: "crawl_completed"`, `status` based on `data.status === "completed" ? "done" : "error"`
- `chatbot:status_changed` (ready/setup_failed only) → add entry with `id: crypto.randomUUID()`, `taskName: "chatbot_ready"`, `status: data.setup_status === "ready" ? "done" : "error"`

Each entry shape:
```typescript
interface ActivityEntry {
  id: string;          // task_id or generated
  taskName: string;
  status: "running" | "done" | "error";
  detail?: string;
  current?: number;
  total?: number;
  error?: string;
  timestamp: number;
}
```

Entries auto-remove after 30 seconds when `status: "done"`. Error entries persist until dismissed.

Max 50 entries kept in state (oldest dropped).

### Component: `ActivityConsole`

File: `frontend/src/components/ActivityConsole.tsx`

`<ActivityConsole />` must **always be rendered** (not conditionally with `&&`) within an authenticated session. The hook's state must persist across visibility changes. Use CSS (`opacity-0 pointer-events-none` or similar) to hide the toggle button when the entries array is empty. The component unmounts on logout (inside `<ProtectedRoute>`) — that is expected and acceptable.

**Collapsed state:** Small fixed button at `bottom-4 right-4` (inside `<ProtectedRoute>`, after `<ToastProvider />`). Shows count of running tasks as badge.

**Expanded state:** ~320px wide, max 400px tall, scrollable. Reverse chronological order.

Each entry row:
- Spinner icon (running), checkmark (done), or x-circle (error)
- Human-readable label (mapped from `task_name`)
- Detail text in muted color
- Progress bar if `current`/`total` present
- Relative timestamp ("3s ago")
- Dismiss button on error entries

**Task name labels:**

```typescript
const TASK_LABELS: Record<string, string> = {
  analyze_conversation: "Analyzing conversation",
  analyze_all: "Analyzing all conversations",
  compute_sentiment: "Computing sentiment trends",
  cluster_gaps: "Clustering gap events",
  weekly_digest: "Sending weekly digest",
  export_data: "Exporting workspace data",
  sync_documents: "Syncing stale documents",
  auto_recharge: "Auto-recharging credits",
  purge_data: "Purging old data",
  crawl_completed: "Website crawl",
  chatbot_ready: "Chatbot configuration",
};
```

Fallback for unknown `task_name`: display the raw `task_name` value.

### Mount point

In `frontend/src/app/(dashboard)/layout.tsx`, add `<ActivityConsole />` inside `<ProtectedRoute>`, after `<ToastProvider />`:

```tsx
<CommandPalette />
<ToastProvider />
<ActivityConsole />
```

### Relationship to existing toasts

`useRealtimeNotifications` stays unchanged. Toasts are brief popups for important moments. The console is a persistent log. Some overlap is intentional — toasts catch attention, the console provides history within the session.

---

## Files

| Action | Path |
|--------|------|
| Modify | `backend/app/services/realtime.py` — add `emit_task_event` helper |
| Modify | `backend/app/workers/tasks/analyze_conversation.py` — add task events |
| Modify | `backend/app/workers/tasks/compute_sentiment_trends.py` — add task events |
| Modify | `backend/app/workers/tasks/cluster_gaps.py` — add task events |
| Modify | `backend/app/workers/tasks/weekly_digest.py` — add task events |
| Modify | `backend/app/workers/tasks/gdpr_export.py` — add task events |
| Modify | `backend/app/workers/tasks/sync_documents.py` — add task events |
| Modify | `backend/app/workers/tasks/auto_recharge.py` — add task events |
| Modify | `backend/app/workers/tasks/purge_old_data.py` — add task events |
| Modify | `backend/app/api/v1/intelligence.py` — emit `analyze_all` started+completed |
| Modify | `frontend/src/lib/types.ts` — add `TaskEvent` |
| Create | `frontend/src/hooks/useActivityConsole.ts` — event subscriptions + state |
| Create | `frontend/src/components/ActivityConsole.tsx` — floating console UI |
| Modify | `frontend/src/app/(dashboard)/layout.tsx` — mount `ActivityConsole` |

## Testing

- Backend: unit test for `emit_task_event` helper (mock `emit_to_workspace`)
- Frontend: unit test for `ActivityConsole` rendering entries from mocked socket events
- Frontend: test auto-dismiss behavior for completed entries
- Manual: trigger intelligence pipeline tasks, verify console shows live updates
