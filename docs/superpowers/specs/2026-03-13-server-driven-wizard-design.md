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
- `active_crawl_job_id: UUID | None` — FK to `CrawlJob` with `ON DELETE SET NULL`, set when the wizard starts a crawl.

**States and transitions:**

| State | Meaning | Transition trigger |
|---|---|---|
| `crawling` | Crawl and document ingestion in progress | Set by `prepare_crawl()` when wizard starts |
| `configuring` | All docs indexed, autoconfig task running | Ingest task atomic update (see below) |
| `ready` | Autoconfig complete, user hasn't saved review yet | Autoconfig task after writing fields to chatbot row |
| `setup_failed` | Autoconfig failed after all retries | Autoconfig task on final failure |
| `done` | User saved step 3 | Frontend PATCH after user saves |
| `null` | Pre-existing bot, treat as `done` | — |

**DB migration:**
```sql
ALTER TABLE chatbots ADD COLUMN setup_status VARCHAR(20) NULL;
ALTER TABLE chatbots ADD COLUMN active_crawl_job_id UUID NULL
  REFERENCES crawl_jobs(id) ON DELETE SET NULL;
```

**Stuck `configuring` recovery:** If a Celery worker dies mid-task before all retries are exhausted, a chatbot can remain permanently at `configuring` without server-side recovery. This is an acceptable operational risk for now — worker restarts re-queue unacked tasks in most cases, and the 5-minute frontend timeout gives users a visible recovery path via the manual retry endpoint. A periodic cleanup job is out of scope for this iteration.

### Backend: autoconfig triggered server-side

**`ingest_document` task change:**

After each document finishes indexing (both the success path and the `_mark_document_failed` path), run the completion check:

1. Load the document's `knowledge_base_id` → query `KnowledgeBase.chatbot_id` (a direct nullable FK on the `knowledge_bases` table — one KB belongs to at most one chatbot in the 1-to-many `Chatbot → KnowledgeBase` relationship). If `chatbot_id IS NULL`, skip the check silently.
2. Count documents in the KB where `status IN ('pending', 'processing')`. If count > 0, not done yet — return.
3. If count == 0, attempt the atomic transition:

```sql
UPDATE chatbots
SET setup_status = 'configuring'
WHERE id = <chatbot_id> AND setup_status = 'crawling'
RETURNING id
```

Only the task that gets a row back fires `run_autoconfig_for_chatbot.delay(str(chatbot_id))`. All others do nothing. This prevents duplicate autoconfig calls even when many ingest tasks finish near-simultaneously.

**New Celery task: `run_autoconfig_for_chatbot`:**

```python
@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_autoconfig_for_chatbot(self, chatbot_id: str):
    asyncio.run(_run(uuid.UUID(chatbot_id)))

async def _run(chatbot_id):
    await engine.dispose()
    async with async_session_factory() as session:
        chatbot = await get_chatbot_by_id(session, chatbot_id)
        kb = chatbot.knowledge_bases[0]  # primary KB (first attached)
        try:
            await autoconfig_service.run(session, chatbot.id, kb.id, chatbot.workspace_id)
            chatbot.setup_status = "ready"
            await session.commit()
        except Exception as exc:
            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc)
            # All retries exhausted
            chatbot.setup_status = "setup_failed"
            await session.commit()
```

`autoconfig_service.run()` already exists at `backend/app/services/autoconfig_service.py` with signature `run(db, chatbot_id, kb_id, workspace_id) -> Chatbot`. The Celery task calls it directly.

**`prepare_crawl()` change** (`backend/app/services/crawl_service.py`):

After creating the `CrawlJob`, update the chatbot that owns the KB:
```python
chatbot.setup_status = "crawling"
chatbot.active_crawl_job_id = job.id
await session.flush()  # within the same transaction
```

`prepare_crawl()` already receives the chatbot ID (via the KB FK chain). If no chatbot owns the KB, skip the update.

**Chatbot API responses** (`backend/app/schemas/chatbot.py`):

Add `setup_status: str | None` and `active_crawl_job_id: UUID | None` to both `ChatbotResponse` (detail) and the list item schema. These are read-only from the frontend's perspective except for the `done` transition (see below).

**Setting `setup_status = "done"` from the frontend:**

Add `setup_status: str | None` to `ChatbotUpdate`. Restrict valid client-supplied values to `["done"]` only (validate in the schema or route handler — any other value is rejected with 422). This keeps the transition path simple without a dedicated endpoint.

### Frontend: `/chatbots/:id/setup` route

New page at `frontend/src/app/(dashboard)/chatbots/[id]/setup/page.tsx`.

On mount, fetches the chatbot and maps `setup_status` to the wizard step:

| `setup_status` | Wizard shows |
|---|---|
| `crawling` | Step 2 — live crawl progress, polls `active_crawl_job_id` every 2s |
| `configuring` | Step 2 — "AI is configuring your bot…" spinner; polls chatbot every 3s until `setup_status == "ready"`. If still `configuring` after 5 minutes, show error: "Configuration is taking longer than expected. You can wait or [retry manually] from settings." Stop polling. |
| `setup_failed` | Step 2 — error state: "Autoconfig failed. Your bot was created but needs manual configuration. [Go to settings →]" |
| `ready` | Step 3 — review form, fields pre-populated from chatbot row |
| `done` or `null` | Redirect to `/chatbots/:id` |

**Step 4 is dropped from the setup page.** After saving step 3 (`setup_status = "done"`), redirect to `/chatbots/:id`. The embed code is available on the chatbot's Deploy tab. This is intentional — the setup page is a setup flow, not an onboarding tour.

**Crawl failure on the setup page:**

When `setup_status == "crawling"` but the polled crawl job has `status == "failed"`, show: "Crawl failed — [error_message from CrawlJob]. Your bot was created but has no knowledge base content. [Delete and start over] or [Go to settings →] to add a knowledge base manually."

**No URL change from setup page:**

The setup page has no Step 1 panel. Users cannot change the URL once the crawl has started. If they want a different URL, the path is: delete the bot (trash icon on overview card) and create a new one. The setup page header shows the crawled URL as read-only context text.

**`/chatbots/new` change:**

Step 1 (URL entry) stays here. After `createChatbot` + `startCrawl` succeed, redirect to `/chatbots/:id/setup`. All wizard state after step 1 is removed from this page.

### Frontend: chatbot overview

Chatbots with `setup_status` in `["crawling", "configuring", "ready", "setup_failed"]` render as a muted card.

**Card design (muted state):**
- Icon background: `bg-gray-100` (not primary color)
- Badge: animated spinner + label (`"Crawling"` / `"Configuring"` / `"Review needed"` / `"Setup failed"`)
- Progress bar: pulsing animated bar for `crawling`; full static bar for `configuring`/`ready`
- Progress text for `crawling`: `"12 / 34 pages"` — sourced from `active_crawl_job_id` crawl status
- Progress text for `configuring`/`ready`: `"Almost there…"` / `"Review your bot →"`
- Stats: show `—` for all metrics
- Click: navigates to `/chatbots/:id/setup`

**Progress data and polling:**

The chatbot list response includes `setup_status` and `active_crawl_job_id`. To get crawl progress counts (`pages_queued / pages_discovered`) without N+1 calls, the chatbot list API response should include a `crawl_progress` nested object when `setup_status == "crawling"`:

```json
{
  "setup_status": "crawling",
  "active_crawl_job_id": "...",
  "crawl_progress": {
    "pages_queued": 12,
    "pages_discovered": 34,
    "docs_indexed": 5,
    "docs_total": 12
  }
}
```

The backend populates this by joining `CrawlJob` when `active_crawl_job_id IS NOT NULL`. The overview polls the chatbot list every 3 seconds only when any card has `setup_status` of `"crawling"` or `"configuring"` (active progress). Cards in `"ready"` or `"setup_failed"` do not require live updates and are not counted as polling triggers.

### What is removed

The frontend's `runAutoconfig()` call in the wizard polling loop is removed. The backend autoconfig endpoint (`POST /chatbots/:id/autoconfig`) is kept — it serves as a manual retry trigger from the settings page.

## Scope boundaries

- No changes to the autoconfig service (`autoconfig_service.py`, `autoconfig.py`)
- No changes to the crawl service discovery/fetch logic
- No changes to the existing chatbot settings pages (`/chatbots/:id/*`)
- The `POST /chatbots/:id/autoconfig` endpoint is kept but no longer called by the wizard

## File map

**Backend — modify:**
- `backend/app/models/knowledge.py` — add `setup_status`, `active_crawl_job_id` to `Chatbot`
- `backend/app/schemas/chatbot.py` — add fields to response and update schemas; add `crawl_progress` to list item
- `backend/app/services/crawl_service.py` — set `setup_status` + `active_crawl_job_id` in `prepare_crawl()`
- `backend/app/workers/tasks/ingest_document.py` — add completion check (success + failure paths) + atomic transition + task dispatch

**Backend — create:**
- `backend/alembic/versions/<hash>_add_chatbot_setup_status.py` — migration
- `backend/app/workers/tasks/run_autoconfig.py` — new Celery task

**Frontend — modify:**
- `frontend/src/app/(dashboard)/chatbots/new/page.tsx` — step 1 only, redirect after crawl starts
- `frontend/src/app/(dashboard)/chatbots/page.tsx` — muted card for in-progress bots, 3s polling
- `frontend/src/lib/types.ts` — add `setup_status`, `active_crawl_job_id`, `crawl_progress` to `Chatbot` type
- `frontend/src/lib/api-functions.ts` — no signature changes; response type update flows from types.ts

**Frontend — create:**
- `frontend/src/app/(dashboard)/chatbots/[id]/setup/page.tsx` — new setup route

## Testing

**Backend unit tests:**
- `tests/unit/test_ingest_completion_check.py`: atomic transition fires autoconfig task exactly once even if multiple tasks call the check simultaneously; skips silently when `chatbot_id IS NULL`; runs on both success and failure document paths
- `tests/unit/test_run_autoconfig_task.py`: sets `setup_status="ready"` on success; sets `setup_status="setup_failed"` after max retries exhausted

**Backend integration tests:**
- `tests/integration/test_wizard_flow.py`: create chatbot → start crawl → mark all docs indexed → verify `setup_status` transitions `crawling → configuring → ready`

**Frontend unit tests:**
- `src/test/wizard-routing.test.ts`: `getSetupStep(setup_status)` returns correct step for each status value including `null`
- `src/test/chatbot-card.test.ts`: card renders muted vs active based on `setup_status`; progress text correct per state
