# Architecture Overhaul — Pulselight v2

## Executive summary

Strip the codebase from ~43K lines across 6 containers to ~12K lines in 2 containers.
Kill React SPA, Celery, Redis, Socket.IO. Replace with HTMX + Jinja2, asyncio background
tasks, Postgres-as-queue, and native SSE. Keep 3 Preact islands for genuinely interactive UI.

---

## 1. New stack

```
Before (v1):                           After (v2):
─────────────                          ────────────
React SPA (Vite)          →  removed   Jinja2 templates + HTMX + 3 Preact islands
FastAPI + SQLAlchemy       →  keep     FastAPI + SQLAlchemy (slim routes, no service layer)
Celery worker              →  removed   asyncio background tasks (in-process)
Celery beat                →  removed   apscheduler (in-process)
Redis (broker + refresh)   →  removed   Postgres (job queue + session store)
Socket.IO + Redis adapter  →  removed   Native SSE via HTMX
PostgreSQL + pgvector      →  keep     PostgreSQL + pgvector (the only database)
6 Docker containers        →  2        postgres + backend (serves everything)
~9GB RAM dev               →  ~2.5GB   postgres (2GB) + backend (512MB)
```

### Why each removal

| Removed | Reason |
|---------|--------|
| **React SPA** | 70% of pages are CRUD forms/tables. SPA adds 898-line API client, 691-line type duplication, 4 stores, 2 real-time systems. Server-rendered HTML eliminates all of it. |
| **Celery** | 5 task types, none need distributed routing. Every task wraps async code in `asyncio.run()` with an `engine.dispose()` hack. Just call async functions directly. |
| **Celery beat** | Runs ~5 scheduled jobs. Replace with apscheduler in 10 lines. |
| **Redis** | Used for: Celery broker (gone), Socket.IO adapter (gone), refresh token storage (move to Postgres), crawl state cache (move to Postgres). Zero remaining use cases. |
| **Socket.IO** | Used for workspace event broadcasting. Native SSE via HTMX does the same thing with zero client-side code. |

---

## 2. Project structure

```
pulselight/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app, middleware, static files, scheduler
│   │   ├── config.py                  # Settings (trimmed from 103 to ~40 env vars)
│   │   ├── models/                    # SQLAlchemy models (keep as-is, they're fine)
│   │   ├── routes/                    # Route handlers (replaces api/v1/ + services/)
│   │   │   ├── auth.py               # Login, register, refresh, OAuth
│   │   │   ├── chatbots.py           # CRUD + renders templates
│   │   │   ├── sources.py            # Documents, knowledge bases
│   │   │   ├── conversations.py
│   │   │   ├── crawl.py              # Start crawl + SSE progress stream
│   │   │   ├── chat.py               # Public chat SSE endpoint (widget)
│   │   │   ├── settings.py           # Workspace settings, integrations
│   │   │   ├── intelligence.py       # Gaps, sentiment
│   │   │   ├── widget.py             # Widget config + public endpoints
│   │   │   ├── webhooks.py
│   │   │   └── api.py                # JSON-only endpoints (widget config, public chat)
│   │   ├── services/                  # Business logic (only where it earns its keep)
│   │   │   ├── crawler.py            # URL discovery (sitemap + BFS)
│   │   │   ├── fetcher.py            # Page fetching (httpx + Playwright fallback)
│   │   │   ├── rag.py                # Retrieval: hybrid search + RRF + reranking
│   │   │   ├── resolution.py         # Chat resolution: RAG + LLM streaming
│   │   │   ├── ingestion.py          # Extract → chunk → embed → store (one file, not 710 lines)
│   │   │   ├── embedder.py           # FastEmbed wrapper
│   │   │   ├── autoconfig.py         # LLM-powered chatbot auto-configuration
│   │   │   ├── llm.py                # LLM client factory (one file, not 6)
│   │   │   └── integrations/         # Slack, email, linear (keep, they have real logic)
│   │   ├── background/               # Background task infrastructure
│   │   │   ├── runner.py             # asyncio task runner + Postgres job queue
│   │   │   ├── scheduler.py          # apscheduler cron jobs
│   │   │   └── jobs.py               # Job definitions (crawl, ingest, report, etc.)
│   │   ├── realtime/                  # SSE infrastructure
│   │   │   └── events.py             # Workspace subscriber registry + notify helper
│   │   ├── templates/                 # Jinja2 templates
│   │   │   ├── base.html             # Layout: nav, sidebar, toast container, SSE conn
│   │   │   ├── auth/                 # Login, register
│   │   │   ├── chatbots/             # List, detail, sources, deploy, actions, settings
│   │   │   ├── conversations/        # List, detail
│   │   │   ├── intelligence/         # Gaps, sentiment
│   │   │   ├── settings/             # Workspace settings (one page with tabs, not 7 routes)
│   │   │   ├── logs/                 # Crawl/ingest/task logs
│   │   │   └── components/           # Reusable partials (table rows, badges, cards, modals)
│   │   └── static/                   # Served by FastAPI StaticFiles
│   │       ├── css/                  # Tailwind (built at deploy, not at runtime)
│   │       ├── islands/              # Preact islands (3 small bundles)
│   │       │   ├── widget-customizer.tsx
│   │       │   ├── chat-tester.tsx
│   │       │   └── copilot-panel.tsx
│   │       └── widget/               # Embeddable chat widget script (standalone)
│   ├── alembic/                       # DB migrations (keep)
│   └── tests/
├── docker-compose.yml                 # 2 services: postgres + backend
└── Makefile
```

### What merged / deleted

| Before | After |
|--------|-------|
| `api/v1/` (30 files) + `services/` (30 files) | `routes/` (11 files) — routes contain business logic inline for CRUD, call services only for complex operations |
| `schemas/` (22 files, 1,169 lines) | Removed — Pydantic models defined inline where needed, Jinja2 templates don't need response schemas |
| `services/copilot/executor.py` (353 lines) | Deleted — copilot island calls the same routes via fetch |
| `workers/tasks/` (16 files) | `background/jobs.py` (1 file) — plain async functions |
| `workers/celery_app.py` | `background/scheduler.py` — apscheduler |
| `frontend/` (entire directory) | `templates/` + `static/islands/` |

---

## 3. Core flows redesigned

### 3.1 Authentication

```
Before:
  JWT access (30 min) + refresh (7 days in Redis)
  SPA stores tokens in Zustand + localStorage
  Every API call: Authorization: Bearer header
  Refresh via POST /auth/refresh

After:
  HTTP-only secure cookie (session token)
  Session stored in Postgres (sessions table, 7-day expiry)
  Every request: cookie sent automatically
  No refresh flow needed — cookie IS the session
  CSRF protection via SameSite=Lax + CSRF token in forms
```

**Why**: Server-rendered pages don't need bearer tokens. Cookies are simpler, more
secure (no localStorage exposure), and eliminate the entire refresh token dance.
Keep JWT only for the public chat widget API (stateless, no session needed).

```python
# Session middleware — replaces JWT + refresh + Zustand auth store
@app.middleware("http")
async def session_middleware(request: Request, call_next):
    session_id = request.cookies.get("session_id")
    if session_id:
        session = await get_session(db, session_id)  # SELECT from sessions table
        if session and not session.expired:
            request.state.user = session.user
            request.state.workspace = session.workspace
    response = await call_next(request)
    return response
```

```sql
-- sessions table (replaces Redis refresh tokens)
CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,  -- secure random token
    user_id     UUID REFERENCES agents(id),
    workspace_id UUID REFERENCES workspaces(id),
    created_at  TIMESTAMPTZ DEFAULT now(),
    expires_at  TIMESTAMPTZ DEFAULT now() + INTERVAL '7 days',
    ip_address  INET,
    user_agent  TEXT
);
CREATE INDEX idx_sessions_expires ON sessions (expires_at);
-- Periodic cleanup: DELETE FROM sessions WHERE expires_at < now();
```

### 3.2 Page rendering (CRUD)

```
Before (7 layers):
  Browser → React Router → useEffect → api-functions.ts → api.ts
    → fetch(/api/v1/...) → FastAPI route → service function → DB
    → JSON response → Zustand store → React re-render → DOM

After (3 layers):
  Browser → FastAPI route → DB → Jinja2 template → HTML response → DOM
```

Example — chatbot list page:

```python
# routes/chatbots.py
@router.get("/chatbots")
async def list_chatbots(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(
        select(Chatbot)
        .where(Chatbot.workspace_id == workspace.id, Chatbot.archived_at.is_(None))
        .order_by(Chatbot.created_at.desc())
    )
    chatbots = result.scalars().all()
    return templates.TemplateResponse("chatbots/list.html", {
        "request": request,
        "chatbots": chatbots,
    })
```

```html
<!-- templates/chatbots/list.html -->
{% extends "base.html" %}
{% block content %}
<div class="page-header">
  <h1>Chatbots</h1>
  <a href="/chatbots/new" class="btn btn-primary">New chatbot</a>
</div>

<table>
  <thead><tr><th>Name</th><th>Status</th><th>Documents</th><th></th></tr></thead>
  <tbody>
    {% for bot in chatbots %}
    <tr id="chatbot-{{ bot.id }}">
      <td><a href="/chatbots/{{ bot.id }}">{{ bot.name }}</a></td>
      <td>{% include "components/status_badge.html" %}</td>
      <td>{{ bot.document_count }}</td>
      <td>
        <button hx-delete="/chatbots/{{ bot.id }}"
                hx-target="closest tr"
                hx-swap="outerHTML swap:0.2s"
                hx-confirm="Delete {{ bot.name }}?">
          Delete
        </button>
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

No API function. No TypeScript type. No store. No component. One route, one template.

### 3.3 Crawl pipeline (the big redesign)

Current problems:
- BFS capped at 500 URLs
- Fetch concurrency of 5 (17 min for 10K pages)
- One monolithic Celery task — crash = restart from zero
- 10K individual ingest tasks flood the queue
- No batched embedding
- No checkpointing

New design — **streaming pipeline with Postgres job queue**:

```
Phase 1: Discover        Phase 2: Fetch + Ingest (batched)
─────────────────        ─────────────────────────────────
Sitemap or BFS           Fetch pages (concurrency 30)
    │                         │
    ▼                         ▼
Write URLs to             As each page arrives:
  crawl_pages table         extract text → add to chunk buffer
    │                         │
    ▼                         ▼ (every 256 chunks)
Return count              Batch embed → bulk INSERT vectors
  to user                    │
                              ▼
                          Mark documents indexed (checkpoint)
                              │
                          When all done → trigger autoconfig
```

```sql
-- New table: tracks individual page progress (replaces in-memory state)
CREATE TABLE crawl_pages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_job_id    UUID REFERENCES crawl_jobs(id),
    url             TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',  -- pending, fetching, fetched, ingested, failed
    error           TEXT,
    fetched_at      TIMESTAMPTZ,
    ingested_at     TIMESTAMPTZ
);
CREATE INDEX idx_crawl_pages_job_status ON crawl_pages (crawl_job_id, status);
```

```python
# background/jobs.py — the entire crawl pipeline

async def run_crawl(job_id: UUID):
    """Streaming crawl pipeline. Checkpoints every page. Batches embeddings."""
    async with async_session() as db:
        job = await db.get(CrawlJob, job_id)

        # Phase 1: Discover URLs
        urls = await discover_urls(job.root_url, include=job.include_paths, exclude=job.exclude_paths)

        # Write all discovered URLs to crawl_pages (checkpoint: we know what to fetch)
        for url_batch in batched(urls, 100):
            await db.execute(
                insert(CrawlPage),
                [{"crawl_job_id": job_id, "url": u.url, "status": "pending"} for u in url_batch]
            )
        await db.commit()
        await notify_workspace(job.workspace_id, "crawl:progress",
            render_crawl_progress(job, discovered=len(urls), fetched=0))

        # Phase 2: Fetch + ingest in streaming batches
        chunk_buffer = []
        chunk_meta = []  # tracks which doc each chunk belongs to
        fetched = 0
        semaphore = asyncio.Semaphore(30)  # 30 concurrent fetches (not 5)

        async def fetch_page(crawl_page):
            async with semaphore:
                result = await fetch(crawl_page.url)
                return crawl_page, result

        tasks = [asyncio.create_task(fetch_page(p)) for p in pages]

        for coro in asyncio.as_completed(tasks):
            page, result = await coro
            fetched += 1

            if result.status_code >= 400 or not result.text:
                page.status = "failed"
                page.error = f"HTTP {result.status_code}"
                await db.commit()
                continue

            # Create document + chunk immediately
            doc = Document(workspace_id=job.workspace_id, ...)
            db.add(doc)
            await db.flush()

            chunks = chunk_content(result.text)
            for chunk in chunks:
                chunk_buffer.append(chunk["content"])
                chunk_meta.append({"doc_id": doc.id, "heading": chunk.get("heading_path")})

            page.status = "fetched"

            # Batch embed when buffer reaches 256
            if len(chunk_buffer) >= 256:
                embeddings = await embed_chunks(chunk_buffer)
                await bulk_insert_vectors(db, chunk_buffer, chunk_meta, embeddings)
                # Mark all docs in this batch as indexed
                for meta in chunk_meta:
                    await db.execute(
                        update(Document).where(Document.id == meta["doc_id"])
                        .values(status="indexed"))
                await db.commit()  # CHECKPOINT — crash-safe up to here
                chunk_buffer.clear()
                chunk_meta.clear()

            # Progress update (debounced to 1/sec by notify_workspace)
            await notify_workspace(job.workspace_id, "crawl:progress",
                render_crawl_progress(job, discovered=len(urls), fetched=fetched))

        # Flush remaining chunks
        if chunk_buffer:
            embeddings = await embed_chunks(chunk_buffer)
            await bulk_insert_vectors(db, chunk_buffer, chunk_meta, embeddings)
            await db.commit()

        job.status = "completed"
        await db.commit()
        await notify_workspace(job.workspace_id, "crawl:completed",
            render_crawl_completed(job))
```

Key improvements:
- **No 500 URL cap** — configurable limit per plan tier
- **30 concurrent fetches** instead of 5
- **Batched embedding** — 256 chunks at a time instead of per-document
- **Bulk vector INSERT** instead of 10K individual inserts
- **Checkpointing** — every batch commit is a checkpoint. Crash at page 7,342? Resume from 7,100.
- **One async function** instead of 10K Celery tasks

### 3.4 Ingestion (single document upload)

For non-crawl documents (file upload, URL paste, Notion, etc.), the flow is simpler:

```python
# routes/sources.py
@router.post("/chatbots/{chatbot_id}/sources")
async def add_source(chatbot_id: UUID, file: UploadFile = None, url: str = Form(None), ...):
    doc = Document(...)
    db.add(doc)
    await db.commit()

    # Run ingestion in background
    enqueue(ingest_document(doc.id))

    # Return the new document row (HTMX swaps it into the table)
    return templates.TemplateResponse("components/document_row.html", {"doc": doc})
```

```python
# background/jobs.py
async def ingest_document(doc_id: UUID):
    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        content = await extract(doc)             # one function, dispatches by source_type
        chunks = chunk_content(content)           # one function, picks chunker by content
        embeddings = await embed_chunks([c["content"] for c in chunks])
        await bulk_insert_vectors(db, chunks, embeddings)
        doc.status = "indexed"
        await db.commit()
        await notify_workspace(doc.workspace_id, "document:status_changed",
            render_document_row(doc))  # sends HTML, not JSON
```

The current 710-line `pipeline.py` with 6 copy-pasted blocks becomes ~40 lines. The extract/chunk
functions dispatch by type internally — the pipeline doesn't need to know about Notion vs Dropbox.

### 3.5 Chat (public widget) — unchanged architecture, cleaner implementation

The widget is already standalone JS embedded on customer sites. This doesn't change.

```
Customer's site                        Your server
─────────────                          ───────────
<script src="pulselight.js"/>   →   GET /widget/{id}/config (JSON)
User types message              →   POST /api/chat (SSE stream)
                                       ├── RAG retrieval (pgvector + FTS + RRF)
                                       ├── LLM stream (OpenRouter/OpenAI/Anthropic)
                                       └── token events → done event
```

The only change: the chat endpoint stays as a **JSON API** (not server-rendered). The widget
is client-side JS — it needs JSON, not HTML. This lives in `routes/api.py` alongside
widget config.

### 3.6 Real-time updates (SSE)

```python
# realtime/events.py — the entire real-time infrastructure

from asyncio import Queue
from collections import defaultdict

_subscribers: dict[str, set[Queue]] = defaultdict(set)

async def subscribe(workspace_id: str):
    """Returns an async generator of SSE events for this workspace."""
    queue: Queue = Queue()
    _subscribers[workspace_id].add(queue)
    try:
        while True:
            event = await queue.get()
            yield f"event: {event['type']}\ndata: {event['html']}\n\n"
    finally:
        _subscribers[workspace_id].discard(queue)

async def notify_workspace(workspace_id: str, event_type: str, html: str):
    """Push an HTML fragment to all SSE subscribers in a workspace."""
    for queue in _subscribers.get(str(workspace_id), set()):
        await queue.put({"type": event_type, "html": html})
```

```python
# routes/events.py
@router.get("/events/stream")
async def workspace_event_stream(request: Request):
    workspace = request.state.workspace
    return StreamingResponse(
        subscribe(str(workspace.id)),
        media_type="text/event-stream",
    )
```

```html
<!-- templates/base.html — every page gets this -->
<body hx-ext="sse" sse-connect="/events/stream">

  <!-- Toast notifications -->
  <div id="toasts" sse-swap="toast" hx-swap="afterbegin"></div>

  <!-- Any element can be updated out-of-band by ID -->
  {% block content %}{% endblock %}
</body>
```

When the crawl pipeline calls `notify_workspace(ws_id, "crawl:progress", html)`,
the HTML fragment arrives in the browser and HTMX swaps it into the matching element.
No Socket.IO. No Redis. No client-side event handling code.

### 3.7 Background task infrastructure

```python
# background/runner.py — replaces Celery

import asyncio
import logging

logger = logging.getLogger(__name__)
_tasks: set[asyncio.Task] = set()

def enqueue(coro, name: str = None):
    """Fire-and-forget an async coroutine as a background task."""
    task = asyncio.create_task(coro, name=name)
    _tasks.add(task)
    task.add_done_callback(_on_done)

def _on_done(task: asyncio.Task):
    _tasks.discard(task)
    if task.exception():
        logger.exception("Background task %s failed", task.get_name(), exc_info=task.exception())
```

```python
# background/scheduler.py — replaces Celery Beat

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def setup_scheduler():
    scheduler.add_job(cluster_gaps,             "cron", hour=3)
    scheduler.add_job(compute_sentiment_trends,  "cron", hour=4)
    scheduler.add_job(close_stale_conversations, "cron", hour="*/6")
    scheduler.add_job(sync_documents,            "cron", hour=2)
    scheduler.add_job(purge_old_data,            "cron", hour=5, day_of_week="sun")
    scheduler.start()
```

```python
# For crash-resilient jobs (crawls), use Postgres as queue:
# background/runner.py (extended)

async def run_job_worker():
    """Polls Postgres for pending jobs. Runs on startup."""
    while True:
        async with async_session() as db:
            row = await db.execute(text("""
                UPDATE background_jobs SET status='running', started_at=now()
                WHERE id = (
                    SELECT id FROM background_jobs
                    WHERE status='pending'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING *
            """))
            job = row.fetchone()

        if job:
            handler = JOB_HANDLERS.get(job.job_type)
            try:
                await handler(job.payload)
                await mark_job(job.id, "completed")
            except Exception as e:
                if job.attempts < job.max_retries:
                    await mark_job(job.id, "pending", attempts=job.attempts + 1)
                else:
                    await mark_job(job.id, "failed", error=str(e))
        else:
            await asyncio.sleep(1)
```

Two-tier system:
- **Fire-and-forget** (`enqueue`): For quick tasks (webhook delivery, single doc ingest).
  If the process crashes, these are lost — acceptable for non-critical work.
- **Postgres queue** (`background_jobs` table): For long-running, crash-sensitive work
  (crawls, batch ingestion). Survives restarts. Supports retries.

### 3.8 Preact islands (the 3 interactive components)

```html
<!-- templates/chatbots/customize.html -->
{% extends "base.html" %}
{% block content %}
<h1>Customize Widget</h1>

<!-- Server renders the page shell. Preact handles the interactive customizer. -->
<div id="widget-customizer"
     data-chatbot-id="{{ chatbot.id }}"
     data-config='{{ chatbot.widget_config | tojson }}'>
</div>

<script type="module" src="/static/islands/widget-customizer.js"></script>
{% endblock %}
```

Each island is a self-contained Preact component (~3KB runtime vs React's 40KB).
They communicate with the server via `fetch()` to JSON endpoints in `routes/api.py`.

| Island | Purpose | Why it needs client-side |
|--------|---------|------------------------|
| widget-customizer | Live preview as you tweak colors/text | Two-way binding between form + preview |
| chat-tester | Test chat with streaming responses | SSE token streaming into chat bubbles |
| copilot-panel | AI assistant with tool execution | Streaming + dynamic UI updates |

Everything else is server-rendered.

---

## 4. Database changes

### New tables

```sql
-- Replace Redis refresh tokens
CREATE TABLE sessions (
    id           TEXT PRIMARY KEY,
    user_id      UUID REFERENCES agents(id) ON DELETE CASCADE,
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ DEFAULT now(),
    expires_at   TIMESTAMPTZ DEFAULT now() + INTERVAL '7 days',
    ip_address   INET,
    user_agent   TEXT
);

-- Replace Celery
CREATE TABLE background_jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type     TEXT NOT NULL,          -- 'crawl', 'ingest_batch', 'send_report'
    payload      JSONB NOT NULL DEFAULT '{}',
    status       TEXT DEFAULT 'pending', -- pending, running, completed, failed
    attempts     INT DEFAULT 0,
    max_retries  INT DEFAULT 3,
    error        TEXT,
    created_at   TIMESTAMPTZ DEFAULT now(),
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
CREATE INDEX idx_bg_jobs_pending ON background_jobs (status, created_at)
    WHERE status = 'pending';

-- Crawl checkpointing (replaces in-memory tracking)
CREATE TABLE crawl_pages (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_job_id  UUID REFERENCES crawl_jobs(id) ON DELETE CASCADE,
    url           TEXT NOT NULL,
    status        TEXT DEFAULT 'pending',
    error         TEXT,
    fetched_at    TIMESTAMPTZ,
    ingested_at   TIMESTAMPTZ
);
CREATE INDEX idx_crawl_pages_job ON crawl_pages (crawl_job_id, status);
```

### Removed tables

```sql
-- These can be dropped if not already used:
-- webhook_deliveries tracking can move to background_jobs
-- background_task_log replaced by background_jobs
```

---

## 5. Config simplification

```python
# config.py — from 103 env vars to ~40

class Settings(BaseSettings):
    # Database (Postgres only, no Redis)
    DATABASE_URL: str = "postgresql+asyncpg://pulse:pulse_dev_password@postgres:5432/pulse"

    # Auth
    SECRET_KEY: str                          # Signs session cookies + CSRF tokens
    SESSION_EXPIRY_DAYS: int = 7

    # LLM (one primary provider)
    OPENROUTER_API_KEY: str = ""             # Primary LLM provider
    DEFAULT_MODEL: str = "anthropic/claude-sonnet-4-20250514"

    # Embedding
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    # Crawl
    CRAWL_FETCH_CONCURRENCY: int = 30
    CRAWL_MAX_PAGES: int = 10000
    CRAWL_EMBED_BATCH_SIZE: int = 256

    # OAuth (only configure what you use)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Integrations (lazy — only loaded when configured in UI)
    FERNET_KEY: str = ""                     # Encrypts integration tokens at rest

    # Deployment
    CLOUD_MODE: bool = False
    STRIPE_SECRET_KEY: str = ""              # Only needed if CLOUD_MODE=True
    STRIPE_WEBHOOK_SECRET: str = ""

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    CORS_ORIGINS: list[str] = ["*"]
```

OAuth provider credentials (Notion, Slack, Shopify, Zendesk, Dropbox, Salesforce)
are stored in the `integration_configs` table, encrypted with FERNET_KEY. Not in env vars.
Users configure them through the UI.

---

## 6. What stays the same

These parts of the current architecture are good and don't change:

| Component | Why it stays |
|-----------|-------------|
| **SQLAlchemy models** | Clean, well-structured. UUIDPrimaryKeyMixin, TimestampMixin are fine. |
| **RAG pipeline** | Hybrid pgvector + FTS + RRF is solid. Keep retriever.py logic. |
| **LLM client abstraction** | Multi-provider support is needed. Just consolidate 6 files → 1. |
| **Embedder** | FastEmbed local model is the right call. Keep asyncio.to_thread. |
| **Chunkers** | markdown_chunker, qa_chunker, recursive_chunker work well. |
| **Widget script** | Standalone embeddable JS. Unchanged. |
| **Alembic migrations** | Standard, works fine. |
| **Multi-tenant model** | Workspace-scoped everything. Keep the pattern. |

---

## 7. Migration path

Not a rewrite. Incremental migration over ~5 phases.

### Phase 1: Kill Celery + Redis (1-2 days)
1. Add `background/runner.py` (enqueue + Postgres job worker)
2. Add `background/scheduler.py` (apscheduler)
3. Convert each Celery task to a plain async function
4. Add `sessions` table, move refresh tokens from Redis to Postgres
5. Remove `celery_worker`, `celery_beat`, `redis` from docker-compose
6. **Test**: all background jobs run, auth works without Redis

### Phase 2: Add Jinja2 templates alongside React (2-3 days)
1. Add Jinja2 template rendering to FastAPI
2. Add `base.html` with HTMX + SSE
3. Convert settings pages first (pure CRUD, lowest risk)
4. Routes return HTML for browser requests, JSON for API requests
5. **Test**: settings pages work as server-rendered HTML

### Phase 3: Convert remaining CRUD pages (3-4 days)
1. Chatbot list/detail, sources, deploy, actions
2. Conversations list/detail
3. Intelligence pages
4. Logs pages
5. Auth pages (login, register)
6. **Test**: all CRUD flows work without React

### Phase 4: Build Preact islands (1-2 days)
1. Widget customizer island
2. Chat tester island
3. Copilot panel island
4. **Test**: interactive features work within server-rendered pages

### Phase 5: Delete React + cleanup (1 day)
1. Remove `frontend/` directory
2. Remove frontend container from docker-compose
3. Serve static files from FastAPI
4. Delete `api-functions.ts`, `types.ts`, Zustand stores, socket.ts, sse.ts
5. Delete unused backend schemas (response models not needed for templates)
6. Consolidate service layer into routes
7. **Test**: full E2E pass

### Phase 6: Crawl pipeline overhaul (2-3 days)
1. Add `crawl_pages` table
2. Rewrite crawl pipeline with batched embedding + checkpointing
3. Remove 500 URL cap
4. Increase fetch concurrency to 30
5. Implement bulk vector INSERT
6. **Test**: crawl a large site, verify checkpointing works

---

## 8. Performance comparison

| Metric | Current (v1) | Projected (v2) |
|--------|-------------|-----------------|
| **Dev startup** | ~60s (6 containers, model preload) | ~10s (2 containers) |
| **RAM (dev)** | ~9 GB | ~2.5 GB |
| **First page load** | ~800ms (SPA: HTML + JS bundle + API call + render) | ~50ms (server-rendered HTML) |
| **Subsequent navigation** | ~200ms (API call + re-render) | ~100ms (HTMX swap, partial HTML) |
| **10K page crawl** | impossible (500 cap) / ~17 min (if uncapped) | ~5 min (30 concurrency + batch embed) |
| **JS shipped to browser** | ~300 KB (React + deps) | ~17 KB (HTMX 14KB + Preact 3KB, only on interactive pages) |
| **Backend lines** | ~19K | ~8K |
| **Frontend lines** | ~24K | ~3K (templates) + ~1K (islands) |
| **Total codebase** | ~43K lines | ~12K lines |
| **Docker image size** | ~2 GB (backend) + ~500 MB (frontend) | ~800 MB (one image) |
| **Deploy complexity** | 6 containers, Redis, Celery monitoring | 2 containers (Postgres + app) |
| **Production cost (small)** | $40-80/mo (multiple containers) | $10-20/mo (one VPS + managed Postgres) |

---

## 9. What you lose (and whether it matters)

| Lost capability | Impact | Mitigation |
|----------------|--------|------------|
| Client-side routing (instant nav) | Page transitions go from 0ms to 50-100ms | `hx-boost` on `<a>` tags — swaps body without full reload. Feels instant. |
| Optimistic UI updates | Delete/save has ~50ms delay before UI updates | Acceptable for admin dashboard. Not a consumer app. |
| Offline support | None | You never had it anyway. Dashboard requires auth + API. |
| Independent frontend deploys | Must deploy backend to change UI | One less thing to coordinate. Templates are in the same repo. |
| React ecosystem (component libs) | Can't use shadcn, radix, etc. | Tailwind + HTMX + 30 HTML partials. You don't need a component library for tables and forms. |
| Type safety on API boundary | No TypeScript catching bad API calls | There is no API boundary. Templates render from Python objects directly. Type errors are caught by Python. |
| Distributed task processing | Can't scale workers independently | Add Postgres job worker as separate process when needed. One `python worker.py` command. |
