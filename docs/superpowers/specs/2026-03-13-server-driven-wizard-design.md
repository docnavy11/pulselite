# Server-Driven Wizard Design

**Date:** 2026-03-13

## Goal

Move chatbot wizard state from the frontend into the backend so users can navigate away and resume at any point, and in-progress chatbots are visible and resumable from the chatbot overview.

## Problem

The current wizard orchestrates everything from the frontend: it polls the crawl job, detects completion, and triggers autoconfig. If the user navigates away, closes the tab, or refreshes, autoconfig never runs and the chatbot is left in a half-configured state with no recovery path. The chatbot overview has no indication that a bot is still being set up.

## Design

### Backend: `setup_status` state machine

Add two fields to the `Chatbot` model:

- `setup_status: str | None` — tracks wizard progress. `null` on existing bots (treated as `done`).
- `active_crawl_job_id: UUID | None` — FK to `CrawlJob`, set when the wizard starts a crawl.

**States and transitions:**

| State | Meaning | Transition trigger |
|---|---|---|
| `crawling` | Crawl and document ingestion in progress | Set by `prepare_crawl()` when wizard starts |
| `configuring` | All docs indexed, autoconfig task running | Ingest task atomic update (see below) |
| `ready` | Autoconfig complete, user hasn't saved review yet | Autoconfig task after writing fields |
| `done` | User saved step 3 | Frontend PATCH after user saves |
| `null` | Pre-existing bot, treat as done | — |

**DB migration:** Add `setup_status VARCHAR(20) NULL` and `active_crawl_job_id UUID NULL REFERENCES crawl_jobs(id)` to `chatbots`.

### Backend: autoconfig triggered server-side

**`ingest_document` task change:**
After each document finishes indexing, check whether all documents in the KB are in a terminal state (`indexed`, `failed`, or `skipped` — not `pending` or `processing`). If so, attempt an atomic status transition:

```sql
UPDATE chatbots
SET setup_status = 'configuring'
WHERE id = <chatbot_id> AND setup_status = 'crawling'
RETURNING id
```

Only the task that wins this race fires `run_autoconfig_for_chatbot.delay(chatbot_id)`. All others get no rows back and do nothing. This prevents duplicate autoconfig calls.

**New Celery task: `run_autoconfig_for_chatbot`:**
- Loads chatbot and its primary KB
- Calls `autoconfig_service.run(session, chatbot_id, kb_id, workspace_id)` — already exists
- On success: sets `chatbot.setup_status = "ready"`, commits
- On failure: sets `chatbot.setup_status = "crawling"` to allow retry (or leaves as `configuring` with an error flag — keep it simple: log and leave as `configuring` so the frontend can detect a stuck state)
- Max 2 retries (matches existing autoconfig endpoint behaviour)

**`prepare_crawl()` change:**
After creating the `CrawlJob`, also update the chatbot:
```python
chatbot.setup_status = "crawling"
chatbot.active_crawl_job_id = job.id
```

**Chatbot API responses:**
Expose `setup_status` and `active_crawl_job_id` in the chatbot list and detail responses so the frontend can render state correctly.

### Frontend: `/chatbots/:id/setup` route

New route that replaces the wizard for steps 2–4. On mount it reads `chatbot.setup_status` and positions the wizard:

| `setup_status` | Wizard shows |
|---|---|
| `crawling` | Step 2 — crawl progress, polls `active_crawl_job_id` |
| `configuring` | Step 2 — "AI configuring…" phase, polls chatbot until `setup_status == "ready"` |
| `ready` | Step 3 — review form, fields pre-populated from chatbot row |
| `done` or `null` | Redirect to `/chatbots/:id` |

The setup page is a slimmed-down version of the current `new/page.tsx` wizard — it drops step 1 (URL input) and the local-state orchestration. Steps 2 and 3 read from the backend.

**`/chatbots/new` change:**
Step 1 (URL entry) stays here. After `createChatbot` + `startCrawl` succeed, redirect to `/chatbots/:id/setup` instead of advancing local wizard state.

### Frontend: chatbot overview

Chatbots with `setup_status` in `["crawling", "configuring", "ready"]` render as a muted card with a live progress bar:

- **Icon background:** gray (`bg-gray-100`) instead of primary color
- **Badge:** animated spinner + label — `"Crawling"` (crawling), `"Configuring"` (configuring), `"Review needed"` (ready)
- **Progress bar:** pulsing bar under the bot name (for `crawling`); static bar at ~100% for `configuring`/`ready`
- **Progress text:** `"12 / 34 pages"` for `crawling` (polled from `active_crawl_job_id`), `"Almost there…"` for `configuring`
- **Click:** navigates to `/chatbots/:id/setup`
- Stats show `—` for all metrics (no conversations yet)

The overview polls in-progress cards every 3 seconds (only when any card has a non-done status) to update progress numbers.

### What is removed

The frontend's `runAutoconfig()` call in the wizard polling loop is removed. The backend autoconfig endpoint (`POST /chatbots/:id/autoconfig`) is kept as-is — it can serve as a manual retry trigger from the settings page.

## Scope boundaries

- No changes to the autoconfig service (`autoconfig_service.py`, `autoconfig.py`) — already fixed in the previous task
- No changes to the crawl service or ingest extractors
- No changes to the existing chatbot settings pages (`/chatbots/:id/*`)
- The `POST /chatbots/:id/autoconfig` endpoint is kept but no longer called by the wizard

## File map

**Backend — modify:**
- `backend/app/models/knowledge.py` — add `setup_status`, `active_crawl_job_id` to `Chatbot`
- `backend/app/schemas/chatbot.py` — expose new fields in response schemas
- `backend/app/services/crawl_service.py` — set `setup_status` + `active_crawl_job_id` in `prepare_crawl()`
- `backend/app/workers/tasks/ingest_document.py` — add completion check + atomic transition + task dispatch

**Backend — create:**
- `backend/alembic/versions/<hash>_add_chatbot_setup_status.py` — migration
- `backend/app/workers/tasks/run_autoconfig.py` — new Celery task

**Frontend — modify:**
- `frontend/src/app/(dashboard)/chatbots/new/page.tsx` — step 1 only, redirect after crawl starts
- `frontend/src/app/(dashboard)/chatbots/page.tsx` — muted card for in-progress bots, polling
- `frontend/src/lib/types.ts` — add `setup_status`, `active_crawl_job_id` to `Chatbot` type
- `frontend/src/lib/api-functions.ts` — update chatbot response types

**Frontend — create:**
- `frontend/src/app/(dashboard)/chatbots/[id]/setup/page.tsx` — new setup route

## Testing

**Backend unit tests:**
- `test_ingest_document.py`: verify atomic transition fires autoconfig task exactly once when multiple ingest tasks finish concurrently
- `test_run_autoconfig_task.py`: verify task sets `status="ready"` after success

**Backend integration tests:**
- `test_wizard_flow.py`: full flow — create chatbot → start crawl → simulate docs indexed → verify `setup_status` transitions correctly

**Frontend unit tests:**
- `wizard-routing.test.ts`: `getWizardStep(setup_status)` returns correct step for each status
- `chatbot-card.test.ts`: card renders muted/active based on `setup_status`
