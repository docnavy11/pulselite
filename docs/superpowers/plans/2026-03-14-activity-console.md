# Activity Console Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a floating, app-wide activity console showing real-time updates from all Celery background tasks via Socket.IO.

**Architecture:** Add a generic `emit_task_event()` helper to the existing realtime module. Instrument 8 silent Celery tasks with `task:started`/`task:completed` events. Build a React floating console component that subscribes to these events plus existing domain events.

**Tech Stack:** Python (Socket.IO via `emit_to_workspace`), React, TypeScript, Tailwind CSS, `useSocketEvent` hook.

**Spec:** `docs/superpowers/specs/2026-03-14-activity-console-design.md`

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/services/realtime.py` | Add `emit_task_event` helper |
| Modify | `backend/app/workers/tasks/analyze_conversation.py` | Add task events |
| Modify | `backend/app/workers/tasks/compute_sentiment_trends.py` | Add `bind=True` + task events |
| Modify | `backend/app/workers/tasks/cluster_gaps.py` | Add `bind=True` + task events |
| Modify | `backend/app/workers/tasks/weekly_digest.py` | Add `bind=True` + task events |
| Modify | `backend/app/workers/tasks/gdpr_export.py` | Add task events |
| Modify | `backend/app/workers/tasks/sync_documents.py` | Add `bind=True` + restructure + task events |
| Modify | `backend/app/workers/tasks/auto_recharge.py` | Add task events |
| Modify | `backend/app/workers/tasks/purge_old_data.py` | Add `bind=True` + task events |
| Modify | `backend/app/api/v1/intelligence.py` | Emit `analyze_all` events from endpoint |
| Modify | `frontend/src/lib/types.ts` | Add `TaskEvent` interface |
| Create | `frontend/src/hooks/useActivityConsole.ts` | Event subscriptions + state management |
| Create | `frontend/src/components/ActivityConsole.tsx` | Floating console UI |
| Modify | `frontend/src/app/(dashboard)/layout.tsx` | Mount `ActivityConsole` |
| Create | `backend/tests/unit/test_emit_task_event.py` | Unit tests for helper |
| Create | `frontend/src/test/activity-console.test.ts` | Frontend unit tests |

---

## Chunk 1: Backend — emit_task_event helper + tests

### Task 1: Add `emit_task_event` helper to realtime module

**Files:**
- Modify: `backend/app/services/realtime.py`
- Create: `backend/tests/unit/test_emit_task_event.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_emit_task_event.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_emit_task_event_started():
    """emit_task_event emits task:started with correct payload."""
    mock_mgr = AsyncMock()
    with patch("app.services.realtime._create_manager", return_value=mock_mgr):
        from app.services.realtime import emit_task_event

        await emit_task_event(
            workspace_id="ws-abc",
            event_type="started",
            task_name="analyze_conversation",
            task_id="task-123",
            detail="Processing conversation",
        )

        mock_mgr.emit.assert_awaited_once_with(
            "task:started",
            {
                "task_name": "analyze_conversation",
                "task_id": "task-123",
                "detail": "Processing conversation",
                "current": None,
                "total": None,
                "error": None,
            },
            room="ws-abc",
        )


@pytest.mark.asyncio
async def test_emit_task_event_completed_with_error():
    """emit_task_event emits task:completed with error field."""
    mock_mgr = AsyncMock()
    with patch("app.services.realtime._create_manager", return_value=mock_mgr):
        from app.services.realtime import emit_task_event

        await emit_task_event(
            workspace_id="ws-abc",
            event_type="completed",
            task_name="export_data",
            task_id="task-456",
            error="Workspace not found",
        )

        mock_mgr.emit.assert_awaited_once_with(
            "task:completed",
            {
                "task_name": "export_data",
                "task_id": "task-456",
                "detail": None,
                "current": None,
                "total": None,
                "error": "Workspace not found",
            },
            room="ws-abc",
        )


@pytest.mark.asyncio
async def test_emit_task_event_progress():
    """emit_task_event emits task:progress with current/total."""
    mock_mgr = AsyncMock()
    with patch("app.services.realtime._create_manager", return_value=mock_mgr):
        from app.services.realtime import emit_task_event

        await emit_task_event(
            workspace_id="ws-abc",
            event_type="progress",
            task_name="cluster_gaps",
            task_id="task-789",
            current=3,
            total=10,
        )

        mock_mgr.emit.assert_awaited_once_with(
            "task:progress",
            {
                "task_name": "cluster_gaps",
                "task_id": "task-789",
                "detail": None,
                "current": 3,
                "total": 10,
                "error": None,
            },
            room="ws-abc",
        )


@pytest.mark.asyncio
async def test_emit_task_event_uuid_workspace_id():
    """emit_task_event converts UUID workspace_id to string."""
    import uuid

    mock_mgr = AsyncMock()
    ws_uuid = uuid.UUID("350863e7-3dc8-430e-bc23-fd41d4499d7b")
    with patch("app.services.realtime._create_manager", return_value=mock_mgr):
        from app.services.realtime import emit_task_event

        await emit_task_event(
            workspace_id=ws_uuid,
            event_type="started",
            task_name="export_data",
            task_id="task-1",
        )

        mock_mgr.emit.assert_awaited_once()
        call_args = mock_mgr.emit.call_args
        assert call_args[1]["room"] == "350863e7-3dc8-430e-bc23-fd41d4499d7b"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest tests/unit/test_emit_task_event.py -v`
Expected: FAIL with `ImportError` or `AttributeError` — `emit_task_event` does not exist yet.

- [ ] **Step 3: Implement `emit_task_event`**

Add to the end of `backend/app/services/realtime.py` (after the existing `emit_to_workspace` function):

```python
async def emit_task_event(
    workspace_id: str | uuid.UUID,
    event_type: str,
    task_name: str,
    task_id: str,
    detail: str | None = None,
    current: int | None = None,
    total: int | None = None,
    error: str | None = None,
) -> None:
    """Emit a generic task lifecycle event (started/progress/completed).

    Safe to call from API server or Celery worker async context.
    """
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

**Important:** Also add `import uuid` at the top of the file (after the existing imports). The file currently imports `logging` and `typing.Any` — add `import uuid` as the very first change, before appending the function. Without it, the `str | uuid.UUID` type annotation will cause a `NameError`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/unit/test_emit_task_event.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/realtime.py backend/tests/unit/test_emit_task_event.py
git commit -m "feat: add emit_task_event helper to realtime module"
```

---

## Chunk 2: Backend — Instrument workspace-scoped Celery tasks

These three tasks already have `workspace_id` as an argument and already use `bind=True` (or need minimal changes).

### Task 2: Add task events to `analyze_conversation`

**Files:**
- Modify: `backend/app/workers/tasks/analyze_conversation.py`

The task already has `bind=True` and receives `workspace_id`. Skip behavior: do not emit if already analyzed (early return at line 54) or no messages (line 62).

- [ ] **Step 1: Add import**

Add at the top of `backend/app/workers/tasks/analyze_conversation.py`, after the existing imports:

```python
from app.services.realtime import emit_task_event
```

- [ ] **Step 2: Pass `task_id` into the async helper**

Change the `asyncio.run` call in the task function (line 38) to pass `self.request.id`:

```python
return asyncio.run(_analyze(uuid.UUID(conversation_id), uuid.UUID(workspace_id), self.request.id))
```

Update `_analyze` signature (line 43) to accept `task_id`:

```python
async def _analyze(conversation_id: uuid.UUID, workspace_id: uuid.UUID, task_id: str) -> dict:
```

- [ ] **Step 3: Add emit calls inside `_analyze`**

After the idempotency check passes (after line 54's early return) and after the "no messages" check (after line 62), add `started` before the LLM call and `completed` after commit:

After line 63 (`transcript = _build_transcript(messages)`) — before the LLM call, insert:

```python
        await emit_task_event(workspace_id, "started", "analyze_conversation", task_id)
```

After line 83 (`return {"status": "success", ...}`) — replace with:

```python
            await session.commit()
            await emit_task_event(workspace_id, "completed", "analyze_conversation", task_id)
            return {"status": "success", "conversation_id": str(conversation_id)}
```

In the except block (line 84-86), add an error emit before the raise:

```python
        except Exception as exc:
            await session.rollback()
            await emit_task_event(workspace_id, "completed", "analyze_conversation", task_id, error=str(exc))
            raise
```

- [ ] **Step 4: Run existing tests**

Run: `docker compose exec backend pytest tests/ -k "analyze" -v`
Expected: PASS (existing tests should still pass)

- [ ] **Step 5: Commit**

```bash
git add backend/app/workers/tasks/analyze_conversation.py
git commit -m "feat: add task events to analyze_conversation"
```

### Task 3: Add task events to `export_workspace_data`

**Files:**
- Modify: `backend/app/workers/tasks/gdpr_export.py`

Already has `bind=True` and receives `workspace_id`.

- [ ] **Step 1: Add import and pass task_id**

Add import at top:
```python
from app.services.realtime import emit_task_event
```

Change `asyncio.run` call (line 25) to pass `self.request.id`:
```python
return asyncio.run(_export(uuid.UUID(workspace_id), export_id, self.request.id))
```

Update `_export` signature (line 30):
```python
async def _export(workspace_id: uuid.UUID, export_id: str, task_id: str) -> dict:
```

- [ ] **Step 2: Add emit calls inside `_export`**

After the workspace existence check (after line 40's `return {"status": "error", ...}`) — once we know the workspace exists:
```python
            await emit_task_event(workspace_id, "started", "export_data", task_id)
```

After line 93 (the successful return) — replace with:
```python
            await emit_task_event(workspace_id, "completed", "export_data", task_id,
                                  detail=f"Exported {len(contacts)} contacts, {len(conversations)} conversations")
            return {"status": "success", "export_id": export_id, "path": export_path}
```

In the except block (line 94-96), add before the raise:
```python
            await emit_task_event(workspace_id, "completed", "export_data", task_id, error=str(exc))
```

(Change `except Exception:` to `except Exception as exc:`)

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/tasks/gdpr_export.py
git commit -m "feat: add task events to export_workspace_data"
```

### Task 4: Add task events to `trigger_auto_recharge`

**Files:**
- Modify: `backend/app/workers/tasks/auto_recharge.py`

Already has `bind=True` and receives `workspace_id`. Skip behavior: no emit if auto-recharge disabled (line 39) or balance sufficient (line 45).

- [ ] **Step 1: Add import and pass task_id**

Add import:
```python
from app.services.realtime import emit_task_event
```

Change `asyncio.run` call (line 22) to pass `self.request.id`:
```python
return asyncio.run(_recharge(uuid.UUID(workspace_id), self.request.id))
```

Update `_recharge` signature (line 27):
```python
async def _recharge(workspace_id: uuid.UUID, task_id: str) -> dict:
```

- [ ] **Step 2: Add emit calls inside `_recharge`**

The three early-exit returns (lines 36, 39, 44) should stay silent — no emit.

After line 47 (`amount = workspace.auto_recharge_amount`) — task begins real work:
```python
            await emit_task_event(workspace_id, "started", "auto_recharge", task_id)
```

After line 80 (the successful return) — replace with:
```python
            await emit_task_event(workspace_id, "completed", "auto_recharge", task_id,
                                  detail=f"Added {amount} credits")
            return {"status": "success", "credits_added": amount, "new_balance": new_balance}
```

In the outer except block (lines 83-86), add before the return:
```python
            await emit_task_event(workspace_id, "completed", "auto_recharge", task_id, error=str(e))
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/tasks/auto_recharge.py
git commit -m "feat: add task events to trigger_auto_recharge"
```

---

## Chunk 3: Backend — Instrument global Celery tasks (workspace-iterating)

These tasks iterate workspaces internally. Each needs `bind=True` added and per-workspace `started`/`completed` events.

### Task 5: Add task events to `compute_sentiment_trends`

**Files:**
- Modify: `backend/app/workers/tasks/compute_sentiment_trends.py`

Currently `@celery_app.task` (no `bind=True`). Iterates workspace IDs at line 34.

- [ ] **Step 1: Add `bind=True` and import**

Change decorator (line 18):
```python
@celery_app.task(bind=True)
def compute_sentiment_trends(self) -> dict:
```

Change `asyncio.run` call (line 20):
```python
    return asyncio.run(_compute(self.request.id))
```

Add import:
```python
from app.services.realtime import emit_task_event
```

Update `_compute` signature (line 23):
```python
async def _compute(task_id: str) -> dict:
```

- [ ] **Step 2: Add per-workspace emit calls inside `_compute`**

In the workspace loop (line 34-37), wrap the `_compute_workspace` call:

```python
            for ws_id in workspace_ids:
                await emit_task_event(ws_id, "started", "compute_sentiment", task_id)
                alert = await _compute_workspace(session, ws_id)
                if alert:
                    alerts.append(str(ws_id))
                await emit_task_event(ws_id, "completed", "compute_sentiment", task_id)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/tasks/compute_sentiment_trends.py
git commit -m "feat: add task events to compute_sentiment_trends"
```

### Task 6: Add task events to `cluster_gaps`

**Files:**
- Modify: `backend/app/workers/tasks/cluster_gaps.py`

Currently `@celery_app.task(time_limit=600)` (no `bind=True`). Iterates workspace counts at line 41. Emit calls go in `_cluster()`'s for-loop, wrapping `_cluster_workspace()`.

- [ ] **Step 1: Add `bind=True` and import**

Change decorator (line 15):
```python
@celery_app.task(bind=True, time_limit=600)
def cluster_gaps(self) -> dict:
```

Change `asyncio.run` call (line 17):
```python
    return asyncio.run(_cluster(self.request.id))
```

Add import:
```python
from app.services.realtime import emit_task_event
```

Update `_cluster` signature (line 20):
```python
async def _cluster(task_id: str) -> dict:
```

- [ ] **Step 2: Add per-workspace emit calls in `_cluster`**

In the workspace loop (lines 41-50), wrap the `_cluster_workspace` call:

```python
            for ws_id, count in workspace_counts:
                if ws_id in disabled_ws:
                    logger.info(f"Workspace {ws_id}: gap clustering disabled, skipping")
                    continue
                if count < 10:
                    logger.info(f"Workspace {ws_id}: only {count} unclustered events, skipping (need >= 10)")
                    continue

                await emit_task_event(str(ws_id), "started", "cluster_gaps", task_id,
                                      detail=f"{count} unclustered events")
                clustered = await _cluster_workspace(session, ws_id)
                total_clustered += clustered
                await emit_task_event(str(ws_id), "completed", "cluster_gaps", task_id,
                                      detail=f"Clustered {clustered} events")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/tasks/cluster_gaps.py
git commit -m "feat: add task events to cluster_gaps"
```

### Task 7: Add task events to `send_weekly_digest_task`

**Files:**
- Modify: `backend/app/workers/tasks/weekly_digest.py`

Currently `@celery_app.task` (no `bind=True`). Iterates workspaces at line 33.

- [ ] **Step 1: Add `bind=True` and import**

Change decorator (line 20):
```python
@celery_app.task(bind=True)
def send_weekly_digest_task(self) -> dict:
```

Change `asyncio.run` call (line 22):
```python
    return asyncio.run(_send_digests(self.request.id))
```

Add import:
```python
from app.services.realtime import emit_task_event
```

Update `_send_digests` signature (line 25):
```python
async def _send_digests(task_id: str) -> dict:
```

- [ ] **Step 2: Add per-workspace emit calls**

In the workspace loop (lines 33-40):

```python
            for ws_id in workspace_ids:
                stats = await _compute_weekly_stats(session, ws_id)
                if stats["total"] == 0:
                    continue

                await emit_task_event(ws_id, "started", "weekly_digest", task_id)
                await send_weekly_digest(session, ws_id, stats)
                await send_weekly_digest_email(session, ws_id, stats)
                sent += 1
                await emit_task_event(ws_id, "completed", "weekly_digest", task_id)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/tasks/weekly_digest.py
git commit -m "feat: add task events to send_weekly_digest_task"
```

### Task 8: Add task events to `purge_old_data`

**Files:**
- Modify: `backend/app/workers/tasks/purge_old_data.py`

Currently `@celery_app.task` (no `bind=True`). Iterates workspaces at line 34.

- [ ] **Step 1: Add `bind=True` and import**

Change decorator (line 17):
```python
@celery_app.task(bind=True)
def purge_old_data(self) -> dict:
```

Change `asyncio.run` call (line 19):
```python
    return asyncio.run(_purge(self.request.id))
```

Add import:
```python
from app.services.realtime import emit_task_event
```

Update `_purge` signature (line 22):
```python
async def _purge(task_id: str) -> dict:
```

- [ ] **Step 2: Add per-workspace emit calls**

In the workspace loop (lines 34-67), wrap the per-workspace work:

```python
            for ws_id, retention_days in workspaces:
                cutoff = now - timedelta(days=retention_days)

                id_result = await session.execute(
                    select(Conversation.id).where(
                        Conversation.workspace_id == ws_id,
                        Conversation.created_at < cutoff,
                    )
                )
                conv_ids = [row[0] for row in id_result.all()]

                if not conv_ids:
                    continue

                await emit_task_event(str(ws_id), "started", "purge_data", task_id,
                                      detail=f"Purging {len(conv_ids)} conversations")

                # Delete child rows first to avoid FK violations
                from app.models.conversations import (
                    Message,
                    MessageFeedback,
                    ConversationTag,
                )
                from app.models.intelligence import ConversationAnalysis

                await session.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
                await session.execute(delete(MessageFeedback).where(MessageFeedback.conversation_id.in_(conv_ids)))
                await session.execute(delete(ConversationTag).where(ConversationTag.conversation_id.in_(conv_ids)))
                await session.execute(
                    delete(ConversationAnalysis).where(ConversationAnalysis.conversation_id.in_(conv_ids))
                )
                await session.execute(delete(Conversation).where(Conversation.id.in_(conv_ids)))
                deleted = len(conv_ids)
                total_deleted += deleted
                if deleted:
                    logger.info(f"Workspace {ws_id}: purged {deleted} conversations older than {retention_days} days")

                await emit_task_event(str(ws_id), "completed", "purge_data", task_id,
                                      detail=f"Purged {deleted} conversations")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/tasks/purge_old_data.py
git commit -m "feat: add task events to purge_old_data"
```

### Task 9: Add task events to `sync_stale_documents`

**Files:**
- Modify: `backend/app/workers/tasks/sync_documents.py`

Currently `@celery_app.task` (no `bind=True`). Iterates documents, not workspaces. Needs restructure to group by workspace.

- [ ] **Step 1: Add `bind=True` and import**

Change decorator (line 13):
```python
@celery_app.task(bind=True)
def sync_stale_documents(self) -> dict:
```

Change `asyncio.run` call (line 15):
```python
    result = asyncio.run(_find_and_queue_stale(self.request.id))
```

Add imports at top:
```python
from collections import defaultdict
from app.services.realtime import emit_task_event
```

Update `_find_and_queue_stale` signature (line 19):
```python
async def _find_and_queue_stale(task_id: str) -> dict:
```

- [ ] **Step 2: Restructure to group by workspace and add emit calls**

Replace the loop logic (lines 32-44) with workspace-grouped dispatch:

```python
        documents = result.scalars().all()

        # Group by workspace for per-workspace event emission
        by_ws: dict[str, list] = defaultdict(list)
        for doc in documents:
            doc.status = "stale"
            by_ws[str(doc.workspace_id)].append(str(doc.id))

        await session.commit()  # commit first

        queued = 0
        for ws_id, doc_ids in by_ws.items():
            await emit_task_event(ws_id, "started", "sync_documents", task_id,
                                  detail=f"Syncing {len(doc_ids)} documents")
            for doc_id in doc_ids:
                ingest_document.delay(doc_id)  # then fire tasks
                queued += 1
            await emit_task_event(ws_id, "completed", "sync_documents", task_id,
                                  detail=f"Queued {len(doc_ids)} documents")

        return {"queued": queued}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/workers/tasks/sync_documents.py
git commit -m "feat: add task events to sync_stale_documents"
```

---

## Chunk 4: Backend — Intelligence API endpoint events

### Task 10: Add `analyze_all` events to intelligence endpoint

**Files:**
- Modify: `backend/app/api/v1/intelligence.py`

The `trigger_analyze_all_conversations` endpoint (line 167) dispatches N analyze tasks. Emit a single `task:started` + `task:completed` pair from the endpoint itself using a generated UUID as `task_id`.

- [ ] **Step 1: Add import**

Add at top of `backend/app/api/v1/intelligence.py`:
```python
from app.services.realtime import emit_task_event
```

Ensure `uuid` is imported (it likely already is — verify, add `import uuid` if not).

- [ ] **Step 2: Add emit calls in `trigger_analyze_all_conversations`**

After line 183 (`conversation_ids = ...`) and before the dispatch loop, add:

```python
    task_id = str(uuid.uuid4())
    await emit_task_event(
        workspace_id, "started", "analyze_all", task_id,
        detail=f"Queued {len(conversation_ids)} conversations",
    )
```

After the dispatch loop (after line 186), add:

```python
    await emit_task_event(
        workspace_id, "completed", "analyze_all", task_id,
        detail=f"Dispatched {len(conversation_ids)} analysis tasks",
    )
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/intelligence.py
git commit -m "feat: emit analyze_all task events from intelligence endpoint"
```

---

## Chunk 5: Frontend — Types, hook, component, and layout mount

### Task 11: Add `TaskEvent` type

**Files:**
- Modify: `frontend/src/lib/types.ts`

- [ ] **Step 1: Add interface**

Add after the existing `WorkspaceUsageEvent` interface (after line 521):

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

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat: add TaskEvent type for activity console"
```

### Task 12: Create `useActivityConsole` hook

**Files:**
- Create: `frontend/src/hooks/useActivityConsole.ts`

- [ ] **Step 1: Create the hook file**

Create `frontend/src/hooks/useActivityConsole.ts`:

```typescript
import { useState, useCallback, useEffect, useRef } from "react";
import { useSocketEvent } from "@/lib/socket";
import type { TaskEvent, CrawlCompletedEvent, ChatbotStatusEvent } from "@/lib/types";

export interface ActivityEntry {
  id: string;
  taskName: string;
  status: "running" | "done" | "error";
  detail?: string;
  current?: number;
  total?: number;
  error?: string;
  timestamp: number;
}

const MAX_ENTRIES = 50;
const AUTO_DISMISS_MS = 30_000;

export function useActivityConsole() {
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  // Auto-dismiss completed entries after 30s
  const scheduleDismiss = useCallback((id: string) => {
    const existing = timersRef.current.get(id);
    if (existing) clearTimeout(existing);
    const timer = setTimeout(() => {
      setEntries((prev) => prev.filter((e) => e.id !== id));
      timersRef.current.delete(id);
    }, AUTO_DISMISS_MS);
    timersRef.current.set(id, timer);
  }, []);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      timersRef.current.forEach((timer) => clearTimeout(timer));
    };
  }, []);

  const addEntry = useCallback((entry: ActivityEntry) => {
    setEntries((prev) => {
      const filtered = prev.filter((e) => e.id !== entry.id);
      const next = [entry, ...filtered];
      return next.slice(0, MAX_ENTRIES);
    });
  }, []);

  const updateEntry = useCallback((id: string, updates: Partial<ActivityEntry>) => {
    setEntries((prev) =>
      prev.map((e) => (e.id === id ? { ...e, ...updates } : e))
    );
  }, []);

  const dismissEntry = useCallback((id: string) => {
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
    setEntries((prev) => prev.filter((e) => e.id !== id));
  }, []);

  // task:started
  useSocketEvent<TaskEvent>("task:started", (data) => {
    addEntry({
      id: data.task_id,
      taskName: data.task_name,
      status: "running",
      detail: data.detail ?? undefined,
      timestamp: Date.now(),
    });
  });

  // task:progress
  useSocketEvent<TaskEvent>("task:progress", (data) => {
    updateEntry(data.task_id, {
      current: data.current ?? undefined,
      total: data.total ?? undefined,
      detail: data.detail ?? undefined,
    });
  });

  // task:completed
  useSocketEvent<TaskEvent>("task:completed", (data) => {
    const isError = data.error != null;
    const status = isError ? "error" : "done";

    setEntries((prev) => {
      const existing = prev.find((e) => e.id === data.task_id);
      if (existing) {
        return prev.map((e) =>
          e.id === data.task_id
            ? { ...e, status, detail: data.detail ?? e.detail, error: data.error ?? undefined, timestamp: Date.now() }
            : e
        );
      }
      // Entry may not exist if started event was missed
      return [
        {
          id: data.task_id,
          taskName: data.task_name,
          status,
          detail: data.detail ?? undefined,
          error: data.error ?? undefined,
          timestamp: Date.now(),
        },
        ...prev,
      ].slice(0, MAX_ENTRIES);
    });

    if (!isError) {
      scheduleDismiss(data.task_id);
    }
  });

  // crawl:completed — bridge existing domain event
  useSocketEvent<CrawlCompletedEvent>("crawl:completed", (data) => {
    const isError = data.status === "failed";
    const entry: ActivityEntry = {
      id: data.job_id,
      taskName: "crawl_completed",
      status: isError ? "error" : "done",
      detail: isError
        ? data.error_message ?? "Crawl failed"
        : `${data.pages_queued} pages indexed`,
      error: isError ? (data.error_message ?? "Crawl failed") : undefined,
      timestamp: Date.now(),
    };
    addEntry(entry);
    if (!isError) scheduleDismiss(data.job_id);
  });

  // chatbot:status_changed — bridge existing domain event (ready/setup_failed only)
  useSocketEvent<ChatbotStatusEvent>("chatbot:status_changed", (data) => {
    if (data.setup_status !== "ready" && data.setup_status !== "setup_failed") return;
    const isError = data.setup_status === "setup_failed";
    const id = crypto.randomUUID();
    const entry: ActivityEntry = {
      id,
      taskName: "chatbot_ready",
      status: isError ? "error" : "done",
      detail: isError ? "Auto-configuration failed" : "Chatbot is ready",
      error: isError ? "Auto-configuration failed" : undefined,
      timestamp: Date.now(),
    };
    addEntry(entry);
    if (!isError) scheduleDismiss(id);
  });

  const runningCount = entries.filter((e) => e.status === "running").length;

  return { entries, runningCount, dismissEntry };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useActivityConsole.ts
git commit -m "feat: create useActivityConsole hook"
```

### Task 13: Create `ActivityConsole` component

**Files:**
- Create: `frontend/src/components/ActivityConsole.tsx`

- [ ] **Step 1: Create the component file**

Create `frontend/src/components/ActivityConsole.tsx`:

```tsx
import { useState } from "react";
import { useActivityConsole, type ActivityEntry } from "@/hooks/useActivityConsole";

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

function getLabel(taskName: string): string {
  return TASK_LABELS[taskName] ?? taskName;
}

function relativeTime(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 5) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function StatusIcon({ status }: { status: ActivityEntry["status"] }) {
  if (status === "running") {
    return (
      <svg className="h-4 w-4 animate-spin text-amber-500" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
        <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      </svg>
    );
  }
  if (status === "done") {
    return (
      <svg className="h-4 w-4 text-green-500" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
      </svg>
    );
  }
  return (
    <svg className="h-4 w-4 text-red-500" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
    </svg>
  );
}

function EntryRow({
  entry,
  onDismiss,
}: {
  entry: ActivityEntry;
  onDismiss: (id: string) => void;
}) {
  return (
    <div className="flex items-start gap-2 px-3 py-2 border-b border-gray-100 last:border-0">
      <div className="mt-0.5 shrink-0">
        <StatusIcon status={entry.status} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">
          {getLabel(entry.taskName)}
        </p>
        {entry.detail && (
          <p className="text-xs text-gray-500 truncate">{entry.detail}</p>
        )}
        {entry.current != null && entry.total != null && entry.total > 0 && (
          <div className="mt-1 h-1.5 w-full rounded-full bg-gray-200">
            <div
              className="h-full rounded-full bg-amber-400 transition-all"
              style={{ width: `${Math.min(100, (entry.current / entry.total) * 100)}%` }}
            />
          </div>
        )}
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <span className="text-[10px] text-gray-400">{relativeTime(entry.timestamp)}</span>
        {entry.status === "error" && (
          <button
            onClick={() => onDismiss(entry.id)}
            className="ml-1 text-gray-400 hover:text-gray-600"
            title="Dismiss"
          >
            <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

export function ActivityConsole() {
  const { entries, runningCount, dismissEntry } = useActivityConsole();
  const [expanded, setExpanded] = useState(false);

  // Always rendered, but visually hidden when empty
  const hasEntries = entries.length > 0;

  return (
    <div
      className={`fixed bottom-4 right-4 z-50 transition-opacity ${
        hasEntries ? "opacity-100" : "opacity-0 pointer-events-none"
      }`}
    >
      {expanded ? (
        <div className="w-80 max-h-[400px] bg-white rounded-lg shadow-lg border border-gray-200 flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200">
            <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
              Activity
            </h3>
            <button
              onClick={() => setExpanded(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
          {/* Entries */}
          <div className="overflow-y-auto flex-1">
            {entries.map((entry) => (
              <EntryRow key={entry.id} entry={entry} onDismiss={dismissEntry} />
            ))}
          </div>
        </div>
      ) : (
        <button
          onClick={() => setExpanded(true)}
          className="flex items-center gap-2 px-3 py-2 bg-white rounded-lg shadow-lg border border-gray-200 hover:bg-gray-50 transition-colors"
        >
          <svg className="h-4 w-4 text-gray-500" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
          </svg>
          <span className="text-sm text-gray-600">Activity</span>
          {runningCount > 0 && (
            <span className="flex items-center justify-center h-5 min-w-[20px] px-1 text-xs font-medium text-white bg-amber-500 rounded-full">
              {runningCount}
            </span>
          )}
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ActivityConsole.tsx
git commit -m "feat: create ActivityConsole floating component"
```

### Task 14: Mount `ActivityConsole` in layout

**Files:**
- Modify: `frontend/src/app/(dashboard)/layout.tsx`

- [ ] **Step 1: Add import**

Add import at the top of the file (after existing imports):

```typescript
import { ActivityConsole } from "@/components/ActivityConsole";
```

- [ ] **Step 2: Add component inside ProtectedRoute**

In `DashboardShell`, after `<ToastProvider />` (line 60), add:

```tsx
      <ActivityConsole />
```

The JSX should now read:
```tsx
      <CommandPalette />
      <ToastProvider />
      <ActivityConsole />
    </ProtectedRoute>
```

- [ ] **Step 3: Verify frontend compiles**

Run: `docker compose exec frontend npm run build`
Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/\(dashboard\)/layout.tsx
git commit -m "feat: mount ActivityConsole in dashboard layout"
```

---

## Chunk 6: Frontend tests

### Task 15: Frontend unit tests for ActivityConsole

**Files:**
- Create: `frontend/src/test/activity-console.test.ts`

- [ ] **Step 1: Create test file**

Create `frontend/src/test/activity-console.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

// Mock socket module before importing the hook
const mockHandlers = new Map<string, (data: unknown) => void>();
vi.mock("@/lib/socket", () => ({
  useSocketEvent: (event: string, handler: (data: unknown) => void) => {
    mockHandlers.set(event, handler);
  },
}));

// Must import after mock
import { useActivityConsole } from "@/hooks/useActivityConsole";

function emit(event: string, data: unknown) {
  const handler = mockHandlers.get(event);
  if (handler) handler(data);
}

describe("useActivityConsole", () => {
  beforeEach(() => {
    mockHandlers.clear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("adds entry on task:started", () => {
    const { result } = renderHook(() => useActivityConsole());

    act(() => {
      emit("task:started", {
        task_name: "analyze_conversation",
        task_id: "t-1",
        detail: "Processing",
      });
    });

    expect(result.current.entries).toHaveLength(1);
    expect(result.current.entries[0].status).toBe("running");
    expect(result.current.entries[0].taskName).toBe("analyze_conversation");
    expect(result.current.runningCount).toBe(1);
  });

  it("updates entry on task:progress", () => {
    const { result } = renderHook(() => useActivityConsole());

    act(() => {
      emit("task:started", { task_name: "cluster_gaps", task_id: "t-2" });
    });
    act(() => {
      emit("task:progress", { task_name: "cluster_gaps", task_id: "t-2", current: 3, total: 10 });
    });

    expect(result.current.entries[0].current).toBe(3);
    expect(result.current.entries[0].total).toBe(10);
  });

  it("marks entry as done on task:completed (no error)", () => {
    const { result } = renderHook(() => useActivityConsole());

    act(() => {
      emit("task:started", { task_name: "export_data", task_id: "t-3" });
    });
    act(() => {
      emit("task:completed", { task_name: "export_data", task_id: "t-3", detail: "Done" });
    });

    expect(result.current.entries[0].status).toBe("done");
    expect(result.current.runningCount).toBe(0);
  });

  it("marks entry as error on task:completed with error", () => {
    const { result } = renderHook(() => useActivityConsole());

    act(() => {
      emit("task:started", { task_name: "export_data", task_id: "t-4" });
    });
    act(() => {
      emit("task:completed", { task_name: "export_data", task_id: "t-4", error: "Not found" });
    });

    expect(result.current.entries[0].status).toBe("error");
    expect(result.current.entries[0].error).toBe("Not found");
  });

  it("auto-dismisses completed entries after 30s", () => {
    const { result } = renderHook(() => useActivityConsole());

    act(() => {
      emit("task:started", { task_name: "export_data", task_id: "t-5" });
    });
    act(() => {
      emit("task:completed", { task_name: "export_data", task_id: "t-5" });
    });

    expect(result.current.entries).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(30_000);
    });

    expect(result.current.entries).toHaveLength(0);
  });

  it("does NOT auto-dismiss error entries", () => {
    const { result } = renderHook(() => useActivityConsole());

    act(() => {
      emit("task:started", { task_name: "export_data", task_id: "t-6" });
    });
    act(() => {
      emit("task:completed", { task_name: "export_data", task_id: "t-6", error: "Failed" });
    });

    act(() => {
      vi.advanceTimersByTime(60_000);
    });

    expect(result.current.entries).toHaveLength(1);
    expect(result.current.entries[0].status).toBe("error");
  });

  it("dismissEntry removes an error entry", () => {
    const { result } = renderHook(() => useActivityConsole());

    act(() => {
      emit("task:started", { task_name: "export_data", task_id: "t-7" });
    });
    act(() => {
      emit("task:completed", { task_name: "export_data", task_id: "t-7", error: "Oops" });
    });
    act(() => {
      result.current.dismissEntry("t-7");
    });

    expect(result.current.entries).toHaveLength(0);
  });

  it("bridges crawl:completed event as done entry", () => {
    const { result } = renderHook(() => useActivityConsole());

    act(() => {
      emit("crawl:completed", {
        job_id: "j-1",
        chatbot_id: "c-1",
        status: "completed",
        pages_queued: 42,
        pages_failed: 0,
        error_message: null,
      });
    });

    expect(result.current.entries).toHaveLength(1);
    expect(result.current.entries[0].taskName).toBe("crawl_completed");
    expect(result.current.entries[0].status).toBe("done");
  });

  it("bridges chatbot:status_changed ready event", () => {
    const { result } = renderHook(() => useActivityConsole());

    act(() => {
      emit("chatbot:status_changed", { chatbot_id: "c-1", setup_status: "ready" });
    });

    expect(result.current.entries).toHaveLength(1);
    expect(result.current.entries[0].taskName).toBe("chatbot_ready");
    expect(result.current.entries[0].status).toBe("done");
  });

  it("ignores chatbot:status_changed for non-terminal statuses", () => {
    const { result } = renderHook(() => useActivityConsole());

    act(() => {
      emit("chatbot:status_changed", { chatbot_id: "c-1", setup_status: "crawling" });
    });

    expect(result.current.entries).toHaveLength(0);
  });

  it("caps entries at 50", () => {
    const { result } = renderHook(() => useActivityConsole());

    for (let i = 0; i < 55; i++) {
      act(() => {
        emit("task:started", { task_name: "test", task_id: `t-${i}` });
      });
    }

    expect(result.current.entries.length).toBeLessThanOrEqual(50);
  });
});
```

- [ ] **Step 2: Run frontend tests**

Run: `docker compose exec frontend npx vitest run src/test/activity-console.test.ts`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/test/activity-console.test.ts
git commit -m "test: add unit tests for useActivityConsole hook"
```

---

## Chunk 7: Final verification

### Task 16: Full test suite + manual verification

- [ ] **Step 1: Run backend tests**

Run: `docker compose exec backend pytest tests/unit/ -v`
Expected: All PASS.

- [ ] **Step 2: Run frontend tests**

Run: `docker compose exec frontend npx vitest run`
Expected: All PASS.

- [ ] **Step 3: Run frontend build**

Run: `docker compose exec frontend npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Manual verification**

1. Start the app: `make up`
2. Log in as `test@pulse.dev` / `test`
3. Go to Dashboard, trigger "Analyze all conversations" from Dev Tools
4. Verify the floating console appears at bottom-right with an "Analyzing all conversations" entry
5. Wait for individual analysis tasks to complete — verify entries appear and auto-dismiss after 30s
6. Trigger "Cluster gap events" — verify per-workspace entry appears
7. Trigger "Compute sentiment trends" — verify entry appears

- [ ] **Step 5: Final commit (if any remaining changes)**

```bash
git add -A
git commit -m "feat: activity console - final adjustments"
```
