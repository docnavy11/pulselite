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
- **Schema** (`backend/app/schemas/chatbots.py`): Add `auto_detect_language` to persona update and chatbot response schemas.
- **API** (`backend/app/api/v1/chatbots.py`): No new endpoints. The existing `PUT /chatbots/{chatbot_id}/persona` already handles partial updates — the new field flows through naturally.
- **RAG generator** (`backend/app/services/rag/generator.py`): When `chatbot.auto_detect_language` is true, prepend to the system prompt:
  > "Detect the language of the user's message and always respond in that same language. If unsure, use {chatbot.language} as the default."

**Frontend:**

- **Chatbot settings page** (`frontend/src/app/(dashboard)/chatbots/[id]/settings/page.tsx`): Add a toggle below the existing language selector. When enabled, relabel the language dropdown as "Fallback language."

**Migration:** One new column (`auto_detect_language BOOLEAN DEFAULT FALSE`) on `chatbots` table.

### What doesn't change
No new tables, no new workers, no new dependencies. The LLM handles detection entirely.

---

## Feature 2: Webhook Retry with Dead Letter Queue

### Goal
Make webhook delivery reliable with automatic retries and visibility into failed deliveries.

### Approach
Celery-based retry with exponential backoff (5 attempts over ~4 hours). Failed deliveries are stored for inspection and manual retry.

### Changes

**Backend — New model:**

`WebhookDelivery` (`backend/app/models/webhook_delivery.py`):
- `id: UUID` (PK)
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

Indexes: `(webhook_id, status)`, `(status, next_retry_at)` for retry polling.

**Backend — New Celery task:**

`deliver_webhook` (`backend/app/workers/tasks/deliver_webhook.py`):
1. Creates a `WebhookDelivery` row (status=pending) on first invocation.
2. POSTs payload to webhook URL with existing HMAC signature logic.
3. Timeout per request: 10 seconds.
4. On success (2xx): set `status=delivered`, record `last_status_code`.
5. On failure (non-2xx, timeout, connection error): increment `attempts`, record `last_status_code` and `last_error`.
6. If `attempts < max_attempts`: compute delay from schedule `[60, 300, 900, 3600, 10800]` seconds, set `next_retry_at`, call `self.retry(countdown=delay)`.
7. If `attempts >= max_attempts`: set `status=failed` (dead letter).

**Backend — Refactor existing webhook dispatch:**

Current inline webhook dispatch (in `backend/app/services/webhooks.py` or equivalent) replaced with `deliver_webhook.delay(webhook_id, event_type, payload)`. All deliveries become async and retryable.

**Backend — New API endpoints** (workspace-scoped):

- `GET /api/v1/workspaces/{workspace_id}/webhooks/{webhook_id}/deliveries`
  - Paginated list of deliveries for a webhook.
  - Filterable by `status` (pending / delivered / failed).
  - Sorted by `created_at` descending.
- `POST /api/v1/workspaces/{workspace_id}/webhooks/deliveries/{delivery_id}/retry`
  - Resets a failed delivery: `status=pending`, `attempts=0`, fires `deliver_webhook.delay()`.
  - Returns 404 if delivery not found or not in `failed` status.

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

**Backend — Model update:**

`BackgroundTaskLog` (`backend/app/models/task_log.py`): Ensure these fields exist (add if missing):
- `task_name: str`
- `status: str` (pending / running / completed / failed)
- `started_at: datetime`
- `completed_at: datetime | None`
- `error_message: str | None`
- `retry_count: int` (default 0)
- `duration_ms: int | None` — computed on task completion (`completed_at - started_at` in ms). Avoids repeated datetime math in aggregation queries.

**Backend — New API endpoint:**

`GET /api/v1/workspaces/{workspace_id}/workers/health?window=24h`

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
- All metrics computed via SQL aggregation (COUNT, AVG, PERCENTILE_CONT) on `background_task_logs`.
- `timeseries` buckets by hour (1h/24h windows) or by day (7d window).
- `top_errors` groups by `(task_name, error_message)` and returns top 10 by count.
- p95 computed with `PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)`.
- Tasks are globally scoped (not workspace-scoped) since workers process all workspaces. Endpoint requires admin role.

**Frontend — New "Workers" tab on Logs page:**

`frontend/src/app/(dashboard)/logs/page.tsx`:

- Add "Workers" tab alongside existing Crawl Runs, Documents, Analysis Runs tabs.
- **Top row**: 4 stat cards:
  - Queue depth (pending + running)
  - Throughput/hr
  - Failure rate %
  - Avg duration (across all tasks)
- **Middle**: Time-series bar chart — completed (green) vs failed (red) per time bucket. Uses the `timeseries` response field.
- **Bottom**: Sortable table of task types with columns: Task name, Count, Success rate, Avg duration, P95 duration, Last failure. Clicking a row could expand to show recent individual executions (stretch goal, not MVP).
- **Time window selector**: Buttons for 1h / 24h / 7d in the top-right corner.

**Migration:** Possible column additions to `background_task_logs` if `duration_ms` or `retry_count` don't exist yet.

---

## Out of Scope

- Prometheus/Grafana integration (can be added later on top of the same data)
- Real-time worker metrics via WebSocket (polling on page load is sufficient for MVP)
- Language detection library fallback (LLM-only for now)
- Webhook delivery batching or fan-out
- Per-workspace worker metrics (workers are global)

## Migration Summary

| Feature | Tables | Columns |
|---|---|---|
| Multi-language | — | `chatbots.auto_detect_language` (bool) |
| Webhook retry | `webhook_deliveries` (new) | — |
| Worker health | — | `background_task_logs.duration_ms` (int, if missing) |
