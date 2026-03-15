# Multi-language Auto-detection, Webhook Retry, Worker Health Dashboard

**Date:** 2026-03-15
**Status:** Draft

---

## Feature 1: Multi-language Auto-detection

### Goal
Allow chatbots to automatically detect the visitor's language and respond in kind, without requiring separate chatbots per language.

### Approach
Prompt-engineering only. The LLM detects language from the user's message and responds accordingly. No new dependencies, models, or API calls.

### Changes

**Backend:**

- **Chatbot model** (`backend/app/models/knowledge.py`): Add `auto_detect_language: bool = False` column to the `Chatbot` model.
- **Schemas**:
  - `backend/app/schemas/widget.py` — Add `auto_detect_language: bool | None = None` to the `PersonaUpdate` schema (line 101).
  - `backend/app/schemas/chatbots.py` — Add `auto_detect_language: bool | None = None` to `ChatbotUpdate` and `auto_detect_language: bool` to `ChatbotResponse`.
- **API** (`backend/app/api/v1/chatbots.py`): No new endpoints. The existing `PUT /chatbots/{chatbot_id}/persona` already handles partial updates — the new field flows through naturally.
- **System prompt** (`backend/app/services/rag/prompts.py`): Modify `build_system_prompt()` to handle the language line conditionally:
  - When `chatbot.auto_detect_language` is **false** (default): keep current behavior — `"You respond in {language}."`
  - When `chatbot.auto_detect_language` is **true**: replace the language line with: `"Detect the language of the user's message and always respond in that same language. If unsure, default to {language}."`
  - This requires passing the `auto_detect_language` flag into the template. The `PERSONA_TEMPLATE` should use a `{language_instruction}` placeholder instead of the hardcoded `"You respond in {language}."` line, with `build_system_prompt()` computing the appropriate instruction.

**Frontend:**

- **Setup page** (`frontend/src/app/(dashboard)/chatbots/[id]/setup/page.tsx`): Add a toggle below the existing language selector in the persona review step. When enabled, relabel the language dropdown as "Fallback language."
- **Settings tab** (`frontend/src/app/(dashboard)/chatbots/[id]/SettingsTab.tsx`): If language settings also appear here, add the same toggle for consistency.

**Migration:** One new column (`auto_detect_language BOOLEAN DEFAULT FALSE`) on `chatbots` table.

### What doesn't change
No new tables, no new workers, no new dependencies. The LLM handles detection entirely.

---

## Feature 2: Webhook Retry with Dead Letter Queue

### Goal
Make webhook delivery reliable with automatic retries and visibility into failed deliveries.

### Approach
Celery-based retry with exponential backoff (5 attempts over ~4.2 hours). Failed deliveries are stored for inspection and manual retry.

### Changes

**Backend — New model:**

`WebhookDelivery` (`backend/app/models/webhook_delivery.py`):
- `id: UUID` (PK)
- `workspace_id: UUID` (FK, indexed — follows project convention of direct workspace_id on every model for tenant isolation queries)
- `webhook_id: UUID` (FK → `workspace_webhooks.id`, CASCADE delete)
- `event_type: str` (e.g., `conversation.escalated`)
- `payload: JSON` (full event payload)
- `status: str` (pending / delivered / failed)
- `attempts: int` (default 0)
- `max_attempts: int` (default 5)
- `next_retry_at: datetime | None`
- `last_status_code: int | None`
- `last_error: str | None`
- `created_at: datetime`
- `updated_at: datetime`

Indexes: `(webhook_id, status)`, `(status, next_retry_at)` for retry polling, `(webhook_id, created_at DESC)` for paginated delivery listing.

**Backend — Refactored webhook dispatch (`backend/app/services/webhooks.py`):**

The existing `fire_event()` function remains as the orchestrator. It currently:
1. Queries all active webhooks for a workspace + event_type.
2. Loops over matching webhooks and fires each inline.

New behavior:
1. Same query — find matching webhooks.
2. For each matching webhook: create a `WebhookDelivery` row (status=pending, attempts=0) and commit it.
3. Dispatch `deliver_webhook.delay(delivery_id)` for each delivery.

This preserves the existing call sites (`asyncio.create_task(fire_event(...))` in `resolution_service.py`) unchanged. The `fire_event` function becomes the fan-out orchestrator; the Celery task handles individual delivery + retries.

**Backend — New Celery task:**

`deliver_webhook` (`backend/app/workers/tasks/deliver_webhook.py`):
1. Receives `delivery_id` (not webhook_id) — the `WebhookDelivery` row already exists.
2. Loads the delivery + associated webhook from DB.
3. POSTs payload to webhook URL with existing HMAC signature logic.
4. Timeout per request: 10 seconds.
5. On success (2xx): set `status=delivered`, record `last_status_code`.
6. On failure (non-2xx, timeout, connection error): increment `attempts`, record `last_status_code` and `last_error`.
7. If `attempts < max_attempts`: compute delay from schedule `[60, 300, 900, 3600, 10800]` seconds (total ~4.2 hours), set `next_retry_at`, call `self.retry(countdown=delay)`.
8. If `attempts >= max_attempts`: set `status=failed` (dead letter).

Note: Creating the delivery row in `fire_event` (before dispatching the task) avoids duplicate row creation on retries and means the task always operates on an existing row.

**Backend — New API endpoints** (workspace-scoped, admin-only via `Depends(get_workspace_admin)` — matching existing webhook CRUD):

- `GET /api/v1/workspaces/{workspace_id}/webhooks/{webhook_id}/deliveries`
  - Paginated list of deliveries for a webhook.
  - Filterable by `status` (pending / delivered / failed).
  - Sorted by `created_at` descending.
- `POST /api/v1/workspaces/{workspace_id}/webhooks/{webhook_id}/deliveries/{delivery_id}/retry`
  - Scoped under `{webhook_id}` for consistent URL hierarchy.
  - Validates that `delivery.webhook_id == webhook_id` and `delivery.workspace_id == workspace_id` (IDOR protection).
  - Only works on deliveries with `status=failed`. Returns 404 otherwise.
  - Resets: `status=pending`, `attempts=0`, dispatches `deliver_webhook.delay(delivery_id)`.

**Frontend:**

- **Webhooks settings page** (`frontend/src/app/(dashboard)/settings/webhooks/page.tsx`):
  - Each webhook row becomes expandable to show recent deliveries.
  - Delivery rows show: event type, status badge (green=delivered, red=failed, yellow=pending), attempts count, timestamp.
  - Failed deliveries get a "Retry" button.
  - Link to see full delivery list for a webhook.

**Migration:** One new table (`webhook_deliveries`).

---

## Feature 3: Worker Health Dashboard

### Goal
Surface Celery worker health metrics (queue depth, failure rates, performance) in the existing Logs page without adding external monitoring infrastructure.

### Approach
SQL aggregation queries on the existing `BackgroundTaskLog` table, rendered in a new "Workers" tab on the Logs page.

### Changes

**Backend — Model check:**

`BackgroundTaskLog` (`backend/app/models/task_log.py`) already has all required fields:
- `task_name: str` ✓
- `status: str` (running / completed / failed) ✓
- `started_at: datetime` ✓
- `completed_at: datetime | None` ✓
- `error: str | None` ✓ (note: field is `error`, not `error_message`)
- `duration_ms: int | None` ✓
- `workspace_id: UUID` ✓

Missing field to add:
- `retry_count: int` (default 0) — tracks how many times a task was retried before the current execution.

**Backend — New API endpoint:**

`GET /api/v1/workspaces/{workspace_id}/workers/health?window=24h`

Workspace-scoped: filters `BackgroundTaskLog` by `workspace_id` so each workspace sees only its own worker metrics. This is consistent with every other endpoint in the codebase. Admin role required via `Depends(get_workspace_admin)`.

Query parameters:
- `window`: `1h`, `24h`, `7d` (default `24h`)

Response shape:
```json
{
  "queue": {
    "pending": 3,
    "running": 2,
    "throughput_per_hour": 45.2
  },
  "reliability": {
    "total": 1082,
    "succeeded": 1050,
    "failed": 32,
    "failure_rate_pct": 2.96,
    "total_retries": 48,
    "top_errors": [
      {"task_name": "ingest_document", "error": "Connection timeout", "count": 12},
      {"task_name": "crawl_website", "error": "HTTP 503", "count": 8}
    ]
  },
  "performance": {
    "by_task": [
      {
        "task_name": "ingest_document",
        "count": 450,
        "success_rate_pct": 97.8,
        "avg_duration_ms": 3200,
        "p95_duration_ms": 8500,
        "last_failure_at": "2026-03-15T10:23:00Z"
      }
    ]
  },
  "timeseries": [
    {"bucket": "2026-03-15T10:00:00Z", "completed": 42, "failed": 1}
  ]
}
```

Implementation notes:
- All metrics computed via SQL aggregation (COUNT, AVG, PERCENTILE_CONT) on `background_task_logs` filtered by `workspace_id`.
- `timeseries` buckets by hour (1h/24h windows) or by day (7d window).
- `top_errors` groups by `(task_name, error)` — note the column is `error`, not `error_message` — and returns top 10 by count.
- p95 computed with `PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)`. Only includes rows where `duration_ms IS NOT NULL` (excludes still-running tasks).
- `queue.pending` and `queue.running` count current tasks regardless of time window (they reflect live state).
- Consider caching results for 30–60 seconds (e.g., Redis with TTL) to avoid expensive aggregation queries on rapid page refreshes. Not required for MVP but recommended before production use at scale.

**Frontend — New "Workers" tab on Logs page:**

`frontend/src/app/(dashboard)/logs/page.tsx`:

- Add "Workers" tab alongside existing Crawl Runs, Documents, Analysis Runs tabs.
- **Top row**: 4 stat cards:
  - Queue depth (pending + running)
  - Throughput/hr
  - Failure rate %
  - Avg duration (across all tasks)
- **Middle**: Time-series bar chart using **Recharts** (already in `package.json`) — completed (green) vs failed (red) per time bucket. Uses the `timeseries` response field.
- **Bottom**: Sortable table of task types with columns: Task name, Count, Success rate, Avg duration, P95 duration, Last failure. Clicking a row could expand to show recent individual executions (stretch goal, not MVP).
- **Time window selector**: Buttons for 1h / 24h / 7d in the top-right corner.

**Migration:** One new column (`retry_count INTEGER DEFAULT 0`) on `background_task_logs`.

---

## Out of Scope

- Prometheus/Grafana integration (can be added later on top of the same data)
- Real-time worker metrics via WebSocket (polling on page load is sufficient for MVP)
- Language detection library fallback (LLM-only for now)
- Webhook delivery batching or fan-out
- Caching for worker health endpoint (recommended post-MVP)

## Migration Summary

| Feature | Tables | Columns |
|---|---|---|
| Multi-language | — | `chatbots.auto_detect_language` (bool, default false) |
| Webhook retry | `webhook_deliveries` (new) | — |
| Worker health | — | `background_task_logs.retry_count` (int, default 0) |
