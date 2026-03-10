# Pulse Lite — Design Document
**Version:** 2.0 | **Date:** 2026-03-10 | **Status:** Canonical spec — supersedes initial.md and pricing.md

---

## 1. Product Overview

Pulse Lite is a **dead-simple website chatbot** — open source (AGPL-3.0), self-hostable, with a managed cloud version.

Paste a URL. The system crawls it, auto-configures the chatbot, and returns a single `<script>` tag. Live in under 2 minutes. No manual configuration required.

Post-launch, the admin dashboard shows what visitors asked that the bot couldn't answer — closing the loop between conversation intelligence and content improvement.

### Core Promise
> *"Paste your URL. Live in 60 seconds. Then it tells you what your site is missing."*

### What It Is NOT
- Not a flow builder (no Botpress-style visual editor)
- Not a live chat tool (no human handoff at MVP)
- Not a multi-LLM picker (one model, works)
- Not Pulse full (no BERTopic, no lead scoring pipeline, no Intercom compat — those are Full Pulse only)

---

## 2. Open Source Model

### License: AGPL-3.0
- Self-hosters: free forever, all features, no limits
- Commercial SaaS built on it: must open-source modifications
- Us: commercial exception as original authors — we run the hosted version commercially

### Two Modes — One Codebase
```
CLOUD_MODE=false   # Self-hosted: single-user, no billing, no usage limits
CLOUD_MODE=true    # Hosted SaaS: multi-tenant, Stripe billing, usage enforcement
```

`CLOUD_MODE=true` gates **only**: Stripe billing, multi-tenancy enforcement, usage limit middleware.
**No features are gated.** All tiers — including free — get the full product.

### Repo
`pulse-lite` (GitHub: github.com/[org]/pulse-lite)

---

## 3. Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend | Next.js 16 + TypeScript + Tailwind CSS | Turbopack stable, `"use cache"` directive, React 19.2 server actions |
| Widget | Vanilla JS + CSS (no framework) | Shadow DOM, ~5kb gzipped |
| Backend API | FastAPI (Python 3.11+) | Async, SSE streaming |
| Database | PostgreSQL 15+ | Primary data store |
| Vector Search | pgvector — HNSW index | Replaces IVFFlat; dynamic, works from row 1, better recall |
| Embedding Model | text-embedding-3-small (OpenAI) | 1536 dimensions |
| LLM | Claude Haiku (Anthropic) | Default; BYOK overrides per workspace |
| Background Jobs | FastAPI BackgroundTasks + lifespan sweep | No Celery/Redis at MVP |
| Auth | Auth.js v5 | Magic link email + Google OAuth |
| Billing | Stripe | CLOUD_MODE=true only |
| Deployment | Docker Compose | Single command, self-host ready |
| CDN | Cloudflare | Widget delivery + edge cache |

### Explicitly Excluded from MVP
- ❌ Redis / Celery
- ❌ Qdrant
- ❌ BERTopic
- ❌ Multiple LLM selection UI
- ❌ Kubernetes
- ❌ SSO/SAML

---

## 4. Repository Structure

```
pulse-lite/
├── apps/
│   ├── web/                        # Next.js 16 (dashboard + landing)
│   │   ├── app/
│   │   │   ├── (marketing)/        # Landing page, pricing
│   │   │   ├── (auth)/             # Login, magic link
│   │   │   └── (dashboard)/        # Protected dashboard routes
│   │   │       ├── page.tsx                # Home / stats
│   │   │       ├── settings/page.tsx       # Bot config
│   │   │       ├── conversations/          # Conversation list + transcript
│   │   │       ├── unanswered/             # Gap feed
│   │   │       ├── embed/page.tsx          # Embed code
│   │   │       └── onboarding/page.tsx     # Conversational setup wizard
│   │   └── public/
│   │       └── widget.js           # Built widget (copied from /widget/dist)
│   └── api/                        # FastAPI backend
│       ├── main.py
│       ├── routers/
│       │   ├── chat.py             # POST /api/chat (SSE)
│       │   ├── setup.py            # POST /api/setup/chat (onboarding agent)
│       │   ├── crawl.py            # POST /api/crawl
│       │   ├── workspaces.py       # CRUD workspace config
│       │   ├── conversations.py
│       │   ├── analytics.py
│       │   └── webhooks.py         # Webhook config CRUD + delivery
│       ├── services/
│       │   ├── crawler.py          # Tiered fetch (httpx + Playwright fallback)
│       │   ├── embedder.py         # OpenAI embeddings
│       │   ├── retriever.py        # pgvector similarity search
│       │   ├── llm.py              # LLM abstraction (Anthropic default, BYOK)
│       │   ├── autoconfig.py       # Auto system prompt / FAQ generation
│       │   ├── intent.py           # Post-conversation intent classification
│       │   └── webhook_dispatcher.py # Outbound webhook delivery
│       ├── models/                 # SQLAlchemy models
│       ├── schemas/                # Pydantic schemas
│       └── db.py
├── widget/                         # Vanilla JS embeddable widget
│   ├── src/
│   │   ├── widget.js               # Main entry
│   │   ├── ui.js                   # DOM / Shadow DOM rendering
│   │   ├── api.js                  # SSE chat client
│   │   └── styles.css              # Injected into Shadow DOM
│   ├── dist/
│   └── build.js                    # esbuild config
├── config/
│   └── tiers.json                  # Tier definitions — edit to customize
├── docker-compose.yml              # Self-host (postgres + api + web)
├── docker-compose.cloud.yml        # Hosted SaaS override
├── .env.example
├── Makefile                        # make dev, make build, make migrate
├── LICENSE                         # AGPL-3.0
└── README.md
```

---

## 5. Database Schema

PostgreSQL + pgvector. **7 tables** (Auth.js v5 manages its own 4 adapter tables separately).

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- 1. WORKSPACES
-- One per chatbot. A user can own/belong to many workspaces.
CREATE TABLE workspaces (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL,
    api_key         TEXT UNIQUE NOT NULL,       -- public key used by widget
    plan            TEXT NOT NULL DEFAULT 'test', -- tier slug from tiers.json
    website_url     TEXT,
    -- Bot configuration
    bot_name        TEXT NOT NULL DEFAULT 'Assistant',
    system_prompt   TEXT,
    welcome_msg     TEXT,
    fallback_msg    TEXT,
    suggested_qs    TEXT[],                     -- static fallback chips
    -- Widget appearance
    color           TEXT NOT NULL DEFAULT '#6366f1',
    avatar_url      TEXT,
    widget_position TEXT NOT NULL DEFAULT 'bottom-right',
    -- Integrations
    booking_url     TEXT,                       -- Calendly/Cal.com link (optional)
    -- BYOK (available on all tiers including free)
    byok_provider   TEXT,                       -- 'openai' | 'anthropic' | 'google' | NULL
    byok_key_enc    TEXT,                       -- Fernet-encrypted API key
    -- Usage tracking (CLOUD_MODE only)
    conv_count_month INTEGER NOT NULL DEFAULT 0,
    conv_reset_at   TIMESTAMPTZ,
    -- Crawl state
    last_crawled_at TIMESTAMPTZ,
    pages_indexed   INTEGER NOT NULL DEFAULT 0,
    crawl_status    TEXT NOT NULL DEFAULT 'idle', -- 'idle'|'crawling'|'error'
    -- Data retention (GDPR)
    retention_days  INTEGER,                    -- NULL = keep forever
    -- Meta
    stripe_customer_id TEXT,
    stripe_sub_id   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_workspaces_api_key ON workspaces(api_key);


-- 2. WORKSPACE_MEMBERS
-- Many-to-many: users (Auth.js) ↔ workspaces with roles.
-- Auth.js adapter manages the `users` table itself.
CREATE TABLE workspace_members (
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL,              -- Auth.js user.id (string UUID)
    role            TEXT NOT NULL DEFAULT 'member', -- 'owner' | 'admin' | 'member'
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workspace_id, user_id)
);

CREATE INDEX idx_members_user ON workspace_members(user_id);


-- 3. DOCUMENTS
-- One row per crawled URL.
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    source_url      TEXT NOT NULL,
    title           TEXT,
    content_hash    TEXT,                       -- MD5 for change detection (P1)
    crawled_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_documents_workspace ON documents(workspace_id);
CREATE UNIQUE INDEX idx_documents_url ON documents(workspace_id, source_url);


-- 4. CHUNKS
-- Chunked + embedded text from documents.
CREATE TABLE chunks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content         TEXT NOT NULL,
    embedding       vector(1536),
    chunk_index     INTEGER NOT NULL,
    token_count     INTEGER,
    metadata        JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_chunks_workspace ON chunks(workspace_id);
-- HNSW: no training needed, works from row 1, better recall than IVFFlat at all volumes.
CREATE INDEX idx_chunks_embedding ON chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
-- Phase 2: upgrade to pgvectorscale StreamingDiskANN at ~1M+ chunks per workspace.


-- 5. CONVERSATIONS
CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    session_id      TEXT NOT NULL,
    intent          TEXT,                       -- 'presales'|'support'|'navigation'|'complaint'|'other'
    has_lead_signal BOOLEAN NOT NULL DEFAULT FALSE,
    visitor_email   TEXT,
    page_url        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ
);

CREATE INDEX idx_conversations_workspace ON conversations(workspace_id);
CREATE INDEX idx_conversations_created ON conversations(workspace_id, created_at);


-- 6. MESSAGES
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,              -- 'user' | 'assistant'
    content         TEXT NOT NULL,
    confidence      FLOAT,                      -- max cosine similarity (assistant only)
    sources         JSONB,                      -- [{url, title}]
    is_fallback     BOOLEAN NOT NULL DEFAULT FALSE,
    thumbs_up       BOOLEAN,                    -- NULL = no rating
    -- is_unanswered always on USER messages (not assistant).
    -- Fallback detection and thumbs-down both mark the user message.
    -- Feed query: SELECT WHERE role='user' AND is_unanswered=TRUE — trivial.
    is_unanswered   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_unanswered ON messages(workspace_id, is_unanswered)
    WHERE is_unanswered = TRUE;


-- 7. WEBHOOKS
CREATE TABLE webhooks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    events          TEXT[] NOT NULL,            -- see webhook events below
    secret          TEXT,                       -- HMAC-SHA256 signing secret
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_webhooks_workspace ON webhooks(workspace_id);
```

### Webhook Events
```
conversation_started
conversation_ended
email_captured
fallback_triggered
thumbs_down
lead_signal_detected
```

---

## 6. Tier Configuration

Tiers are data, not code. Edit `config/tiers.json` to change limits or add tiers. No code changes required.

```json
{
  "tiers": [
    { "id": "test",    "label": "Test",    "conv_limit": 50,     "price_monthly_usd": 0,   "price_annual_usd": 0   },
    { "id": "starter", "label": "Starter", "conv_limit": 1000,   "price_monthly_usd": 19,  "price_annual_usd": 16  },
    { "id": "growth",  "label": "Growth",  "conv_limit": 5000,   "price_monthly_usd": 49,  "price_annual_usd": 41  },
    { "id": "pro",     "label": "Pro",     "conv_limit": 20000,  "price_monthly_usd": 99,  "price_annual_usd": 82  }
  ],
  "byok_discount": 0.5,
  "stripe_price_ids": {
    "starter_monthly":      "",
    "starter_annual":       "",
    "starter_byok_monthly": "",
    "starter_byok_annual":  "",
    "growth_monthly":       "",
    "growth_annual":        "",
    "growth_byok_monthly":  "",
    "growth_byok_annual":   "",
    "pro_monthly":          "",
    "pro_annual":           "",
    "pro_byok_monthly":     "",
    "pro_byok_annual":      ""
  }
}
```

**BYOK rule:** `BYOK price = tier_price × (1 - byok_discount)` at every paid tier. Test tier is always $0 regardless.

**Usage enforcement:**
```python
import json
from pathlib import Path

_tiers = {t["id"]: t for t in json.loads(Path("config/tiers.json").read_text())["tiers"]}

async def check_and_increment_usage(workspace):
    tier = _tiers.get(workspace.plan, _tiers["test"])
    limit = tier["conv_limit"]

    now = datetime.utcnow()
    if workspace.conv_reset_at and now > workspace.conv_reset_at:
        await reset_monthly_counter(workspace.id)

    if workspace.conv_count_month >= limit:
        raise HTTPException(429, detail="Monthly conversation limit reached")

    await increment_conv_counter(workspace.id)
```

Self-hosters: set `CLOUD_MODE=false` and limits are never enforced regardless of `tiers.json`.

---

## 7. Environment Variables

```bash
# ─── MODE ───────────────────────────────────────────────
CLOUD_MODE=false
APP_URL=http://localhost:3000
API_URL=http://localhost:8000

# ─── DATABASE ───────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/pulselite

# ─── AI (default — used when BYOK not set) ──────────────
OPENAI_API_KEY=               # Required: embeddings
ANTHROPIC_API_KEY=            # Required: chat + setup agent + intent classification

# ─── AUTH (Auth.js v5) ──────────────────────────────────
AUTH_SECRET=                  # Random 32-char string
AUTH_URL=http://localhost:3000
AUTH_GOOGLE_ID=               # Optional: Google OAuth
AUTH_GOOGLE_SECRET=

# ─── EMAIL (magic link auth) ────────────────────────────
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_FROM=noreply@yourdomain.com

# ─── ENCRYPTION ─────────────────────────────────────────
ENCRYPTION_KEY=               # Fernet 32-byte key for BYOK key storage

# ─── STRIPE (CLOUD_MODE=true only) ──────────────────────
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
# Individual price IDs are in config/tiers.json

# ─── WIDGET ─────────────────────────────────────────────
NEXT_PUBLIC_WIDGET_URL=http://localhost:3000/widget.js
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Minimum for self-hosted: `DATABASE_URL` + `OPENAI_API_KEY` + `ANTHROPIC_API_KEY` + `AUTH_SECRET` + SMTP.

---

## 8. API Endpoints

### Public (no auth — called by widget)

```
POST   /api/chat
  Body: { key, message, session_id, history: [{role,content}], page_url }
  Response: SSE stream
  Final SSE event: { done: true, sources, confidence, message_id, is_fallback }

POST   /api/chat/feedback
  Body: { message_id, key, thumbs_up: bool }
  Action: if thumbs_up=false → mark preceding user message is_unanswered=TRUE

POST   /api/chat/capture-email
  Body: { key, session_id, email }
  Action: UPDATE conversations SET visitor_email = $1

POST   /api/chat/end-session
  Body: { key, session_id }
  Action: triggers intent classification for this conversation (sendBeacon endpoint)

GET    /api/widget-config?key={api_key}&page={page_url}
  Response: { bot_name, welcome_msg, suggested_qs, color, avatar_url, position }
  Note: suggested_qs are page-contextual if page param provided, fallback to static chips
```

### Protected (Auth.js session or API key header)

```
# Workspaces
GET    /api/workspaces                       # List all workspaces for current user
POST   /api/workspaces                       # Create new workspace
GET    /api/workspaces/{id}                  # Get workspace config
PATCH  /api/workspaces/{id}                  # Update config
DELETE /api/workspaces/{id}                  # Delete workspace + all data
GET    /api/workspaces/{id}/embed-code       # Get embed script tag

# Team
GET    /api/workspaces/{id}/members          # List members
POST   /api/workspaces/{id}/members/invite   # Invite by email
DELETE /api/workspaces/{id}/members/{uid}    # Remove member

# Crawl
POST   /api/crawl                            # Start crawl (BackgroundTask)
  Body: { url, max_pages: int = 50 }
GET    /api/crawl/status                     # Poll progress
DELETE /api/crawl                            # Delete all chunks, reset

# Setup agent
POST   /api/setup/chat                       # Conversational setup SSE stream
  Body: { workspace_id, message, history }

# Conversations
GET    /api/conversations?page&limit&intent
GET    /api/conversations/{id}/messages

# Analytics
GET    /api/analytics/summary
  Response: { convs_today, convs_week, unanswered_count, intent_distribution }

# Unanswered feed
GET    /api/unanswered?page&limit
PATCH  /api/unanswered/resolve               # Body: { content } — marks all matching resolved
POST   /api/unanswered/add-doc               # Body: { content, answer } — saves + triggers embed

# BYOK
POST   /api/byok                             # Body: { provider, api_key } — encrypts + saves
DELETE /api/byok                             # Remove BYOK

# Webhooks
GET    /api/webhooks
POST   /api/webhooks                         # Body: { url, events[], secret? }
PATCH  /api/webhooks/{id}
DELETE /api/webhooks/{id}

# GDPR
GET    /api/gdpr/export                      # Export all workspace data as JSON
DELETE /api/gdpr/purge                       # Delete all conversations + messages

# Stripe (CLOUD_MODE only)
POST   /api/billing/checkout
POST   /api/billing/portal
POST   /api/billing/webhook
```

---

## 9. Crawl Pipeline

**File:** `apps/api/services/crawler.py`

```python
async def crawl_and_index(workspace_id: str, url: str, max_pages: int = 50):

    await update_workspace(workspace_id, crawl_status='crawling')

    # 1. Discover URLs
    # a. Try {url}/sitemap.xml — parse <loc> tags
    # b. Fallback: BFS spider (httpx + BeautifulSoup, same-domain only)
    #    Skip: .pdf, .jpg, .png, .zip, #anchors, ?query params, already-seen
    urls = await discover_urls(url, max_pages)

    # 2. Full retrain — delete existing index for workspace
    await delete_chunks_by_workspace(workspace_id)
    await delete_documents_by_workspace(workspace_id)

    pages_indexed = 0
    all_content = []

    for page_url in urls:
        try:
            # 3. Tiered fetch
            # Try httpx first (~200ms). If extracted text < 500 chars after parsing,
            # fall back to Playwright headless (~2-3s) for JS/SPA sites.
            html = await fetch_url_tiered(page_url)

            # 4. Extract content
            soup = BeautifulSoup(html, 'html.parser')
            for tag in soup(['nav','footer','header','aside',
                             'script','style','noscript','iframe','form','button']):
                tag.decompose()
            title = soup.find('title').get_text(strip=True) if soup.find('title') else page_url
            content = re.sub(r'\s+', ' ', soup.get_text(separator=' ', strip=True)).strip()

            if len(content) < 100:
                continue

            # 5. Sanitize against prompt injection before embedding
            content = sanitize_chunk(content)

            # 6. Store document
            doc = await create_document(workspace_id, page_url, title, content)
            all_content.append({'url': page_url, 'title': title, 'content': content})

            # 7. Sentence-aware chunking
            # Split on sentence boundaries (nltk.sent_tokenize),
            # greedily merge sentences up to 512 tokens, 50-token overlap.
            # Prepend "Title: {title}\n" to every chunk.
            chunks = chunk_text(content, title=title, chunk_size=512, overlap=50)

            # 8. Embed (batch, 100 chunks per API call)
            embeddings = await embed_texts([c['text'] for c in chunks])

            # 9. Store
            await bulk_insert_chunks(workspace_id, doc.id, chunks, embeddings)
            pages_indexed += 1

        except Exception:
            continue  # skip failed pages, log error

    if pages_indexed > 0:
        await auto_configure(workspace_id, all_content)

    await update_workspace(workspace_id,
        crawl_status='idle',
        last_crawled_at=datetime.utcnow(),
        pages_indexed=pages_indexed
    )
```

### Playwright Fallback
```python
async def fetch_url_tiered(url: str) -> str:
    # Fast path
    html = await httpx_get(url, timeout=10)
    text = BeautifulSoup(html, 'html.parser').get_text(strip=True)
    if len(text) >= 500:
        return html

    # JS-rendered fallback (React SPA, Angular, Framer, etc.)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, wait_until='networkidle', timeout=15000)
        html = await page.content()
        await browser.close()
    return html
```

---

## 10. Chat Pipeline (RAG + Streaming)

**File:** `apps/api/routers/chat.py`

```python
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):

    workspace = await get_workspace_by_key(request.key)

    # Rate limiting: 10 req/min per session_id (in-memory, P1: Redis)
    check_rate_limit(request.session_id)

    # Usage limits (CLOUD_MODE only)
    if CLOUD_MODE:
        await check_and_increment_usage(workspace)

    # Booking intent detection (if booking_url configured)
    booking_link = None
    if workspace.booking_url and is_booking_intent(request.message):
        booking_link = workspace.booking_url

    conversation = await get_or_create_conversation(
        workspace.id, request.session_id, request.page_url
    )

    query_embedding = await embed_text(request.message)
    chunks = await similarity_search(workspace.id, query_embedding, limit=5)
    max_confidence = max([c.similarity for c in chunks], default=0.0)

    FALLBACK_THRESHOLD = 0.35

    if max_confidence < FALLBACK_THRESHOLD or not chunks:
        # Mark USER message as unanswered (not assistant message)
        await save_message(conversation.id, workspace.id, 'user',
                           request.message, is_unanswered=True)
        fallback = workspace.fallback_msg or "I don't have that info. Please contact us."
        msg = await save_message(conversation.id, workspace.id, 'assistant',
                                 fallback, confidence=max_confidence, is_fallback=True)

        await dispatch_webhook(workspace.id, 'fallback_triggered', {
            'conversation_id': str(conversation.id),
            'question': request.message
        })
        return stream_text(fallback, is_fallback=True, message_id=str(msg.id))

    # Build prompt
    context = "\n\n".join([
        f"Source: {c.metadata.get('source_url')}\n{c.content}" for c in chunks
    ])
    system = (workspace.system_prompt or '') + """

    Use ONLY the provided context to answer. If the answer isn't in the context, say you don't know.
    Be concise. Cite sources when helpful.
    """ + f"\n\nContext:\n{context}"

    if booking_link:
        system += f"\n\nIf the user wants to book a call or schedule a meeting, include this link: {booking_link}"

    messages = [*request.history[-6:], {'role': 'user', 'content': request.message}]
    llm = get_llm_for_workspace(workspace)

    await save_message(conversation.id, workspace.id, 'user', request.message)

    sources = [{'url': c.metadata.get('source_url'), 'title': c.metadata.get('title')}
               for c in chunks[:3]]
    full_response = ""

    async def generate():
        nonlocal full_response
        async for token in llm.stream(system=system, messages=messages):
            full_response += token
            yield f"data: {json.dumps({'token': token})}\n\n"

        msg = await save_message(conversation.id, workspace.id, 'assistant',
                                 full_response, confidence=max_confidence,
                                 sources=sources, is_unanswered=False)
        yield f"data: {json.dumps({'done': True, 'sources': sources, 'confidence': max_confidence, 'message_id': str(msg.id), 'is_fallback': False})}\n\n"

        background_tasks.add_task(dispatch_webhook, workspace.id, 'conversation_started',
                                  {'conversation_id': str(conversation.id)})

    return EventSourceResponse(generate())
```

### Booking Intent Detection
```python
BOOKING_SIGNALS = [
    'schedule', 'book', 'demo', 'call', 'meeting', 'appointment',
    'talk to', 'speak with', 'get in touch', 'contact sales'
]

def is_booking_intent(message: str) -> bool:
    msg = message.lower()
    return any(signal in msg for signal in BOOKING_SIGNALS)
```

### Intent Classification (Post-Conversation)

Two-path approach — belt and suspenders:

1. **Widget signals end** via `visibilitychange` → `navigator.sendBeacon('/api/chat/end-session', ...)`
2. **Background sweep** in FastAPI lifespan — runs every 10 minutes, classifies all conversations with `intent IS NULL` and last message older than 10 minutes

```python
# lifespan sweep
async def classify_stale_conversations():
    cutoff = datetime.utcnow() - timedelta(minutes=10)
    stale = await get_unclassified_conversations_before(cutoff)
    for conv in stale:
        messages = await get_conversation_messages(conv.id)
        if len(messages) >= 4:  # > 2 turns
            await classify_and_update(conv.id)
```

Classification prompt:
```python
prompt = f"""
Classify this chatbot conversation. Respond as JSON only.

{{"intent": "presales|support|navigation|complaint|other",
  "has_lead_signal": true|false}}

has_lead_signal = true if visitor asked about pricing, compared competitors,
asked about trials, timelines, or onboarding.

Conversation:
{transcript[:3000]}
"""
```

After classification, if `has_lead_signal=true`:
```python
await dispatch_webhook(workspace.id, 'lead_signal_detected', {
    'conversation_id': str(conversation.id),
    'visitor_email': conversation.visitor_email
})
```

---

## 11. Conversational Setup Wizard

**File:** `apps/api/routers/setup.py` + `apps/web/app/(dashboard)/onboarding/page.tsx`

The onboarding experience replaces the traditional multi-step form wizard with a **chatbot that sets up your chatbot**. This is the primary "wow" moment — the setup process IS the product demo.

### UX Layout
```
┌─────────────────────────────────────────────────────────────────────┐
│  Setting up your chatbot                                            │
├──────────────────────────┬──────────────────────────────────────────┤
│                          │                                          │
│  🤖 Assistant            │  LIVE PREVIEW                           │
│  Hi! I'm here to set     │  ┌─────────────────────────────────┐    │
│  up your chatbot.        │  │ Bot name:  [Acme Assistant     ] │    │
│  What's your website?    │  │ Welcome:   [Hi! I can help...  ] │    │
│                          │  │ Color:     [● #4f46e5          ] │    │
│  You                     │  └─────────────────────────────────┘    │
│  acmecorp.com            │                                          │
│                          │  [Widget preview loads here]            │
│  🤖 Assistant            │                                          │
│  Crawling your site...   │                                          │
│  ████████░░ 34/50 pages  │                                          │
│                          │                                          │
│  Done! Found 42 pages.   │                                          │
│  I've set you up as      │                                          │
│  "Acme Assistant"...     │                                          │
│                          │                                          │
│  [message input]  [Send] │  [Skip to manual setup]                 │
└──────────────────────────┴──────────────────────────────────────────┘
```

### Setup Agent Flow
1. Ask for website URL
2. Trigger crawl → stream progress updates
3. Auto-config runs → fills right panel live (bot name, welcome msg, color, FAQ chips)
4. Ask if any changes needed
5. Show embed code + platform guides (WordPress, Squarespace, Wix, HTML)
6. Confirm live

### Setup Agent Backend

**File:** `apps/api/routers/setup.py`

The setup agent uses Claude with tool use. It is NOT the regular RAG pipeline — it has access to setup-specific tools.

```python
SETUP_TOOLS = [
    {
        "name": "crawl_website",
        "description": "Crawl and index the given URL. Returns pages_indexed count.",
        "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
    },
    {
        "name": "update_workspace",
        "description": "Update a workspace config field. Immediately reflected in dashboard preview.",
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "enum": ["bot_name","welcome_msg","color","fallback_msg","suggested_qs"]},
                "value": {}
            },
            "required": ["field", "value"]
        }
    },
    {
        "name": "get_embed_code",
        "description": "Returns the embed script tag for this workspace.",
        "input_schema": {"type": "object", "properties": {}}
    }
]

SETUP_SYSTEM_PROMPT = """
You are a friendly setup assistant for Pulse Lite. Configure the user's chatbot in under 2 minutes.

Flow:
1. Ask for website URL (first message only)
2. Call crawl_website — stream progress in your message
3. Call update_workspace for each auto-generated field — the dashboard updates live
4. Ask if anything needs changing
5. Call get_embed_code and present it clearly
6. Confirm they're live

Be concise. Use tools immediately — don't describe what you're about to do, just do it.
"""
```

The SSE response from `POST /api/setup/chat` streams both text tokens and tool-call events:
```json
// Text token
{"type": "token", "content": "Crawling your site..."}

// Tool call in progress
{"type": "tool_call", "tool": "crawl_website", "status": "running"}

// Tool result — frontend updates preview panel
{"type": "tool_result", "tool": "update_workspace", "field": "bot_name", "value": "Acme Assistant"}

// Done
{"type": "done"}
```

Frontend listens for `tool_result` events and updates the right-panel preview in real-time.

---

## 12. Embeddable Widget

**File:** `widget/src/widget.js` → built to `widget/dist/widget.js` → copied to `apps/web/public/widget.js`

### Embed Code
```html
<script src="https://app.yourdomain.com/widget.js" data-key="ws_abc123"></script>
```
One line. Self-initializing.

### Architecture
```javascript
(function() {
  const script = document.currentScript;
  const API_KEY = script.getAttribute('data-key');
  const API_URL = '__API_URL__';  // replaced at build time

  const SESSION_ID = sessionStorage.getItem('pulse_session') || (() => {
    const id = crypto.randomUUID();
    sessionStorage.setItem('pulse_session', id);
    return id;
  })();

  // 1. Fetch page-contextual config
  fetch(`${API_URL}/api/widget-config?key=${API_KEY}&page=${encodeURIComponent(location.href)}`)
    .then(r => r.json())
    .then(config => initWidget(config));

  function initWidget(config) {
    const host = document.createElement('div');
    document.body.appendChild(host);
    const shadow = host.attachShadow({ mode: 'closed' });

    const style = document.createElement('style');
    style.textContent = WIDGET_CSS;
    shadow.appendChild(style);

    // Render bubble + panel into shadow DOM
    renderBubble(shadow, config);
    renderPanel(shadow, config);
    wireEvents(shadow, config);
  }

  // Session end signal — triggers intent classification
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      navigator.sendBeacon(`${API_URL}/api/chat/end-session`,
        JSON.stringify({ key: API_KEY, session_id: SESSION_ID }));
    }
  });
})();
```

### UI Structure
```
[Chat Bubble] (52px circle, brand color, bottom-right default)
  └── click → toggle panel

[Chat Panel] (360×520px, slide up animation)
  ├── Header: avatar + bot_name + close
  ├── Messages (scrollable)
  │   ├── Welcome message
  │   ├── Suggested question chips (page-contextual, hide after first message)
  │   ├── User messages (right, brand color)
  │   └── Assistant messages (left)
  │       ├── Sources: [1] Page Title ↗
  │       ├── 👎 Thumbs down (subtle)
  │       ├── Booking button (if booking intent detected)
  │       └── Email capture field (if is_fallback=true)
  └── Input: text field + send
      └── "Powered by Pulse Lite" (test/free tier only)
```

### Features
- **Streaming:** EventSource, tokens rendered as they arrive
- **Page-contextual chips:** `page` param sent with config fetch → backend retrieves relevant chunks → generates contextual questions; cached 1hr per (workspace_id, page_url)
- **Email capture:** shown inline when `is_fallback=true` in final SSE event → `POST /api/chat/capture-email`
- **Thumbs down:** marks the preceding user message `is_unanswered=TRUE`
- **Booking button:** rendered when assistant response contains configured `booking_url`
- **Mobile:** full-screen overlay < 480px
- **Dark mode:** `prefers-color-scheme: dark`
- **Session persistence:** `sessionStorage` — new session on tab close

---

## 13. Auto-Configuration

**File:** `apps/api/services/autoconfig.py`

Runs at end of crawl. Only updates fields not already customized by user.

```python
async def auto_configure(workspace_id: str, pages: list[dict]):
    summary = build_summary(pages, max_tokens=6000)
    color = await extract_brand_color(pages[0]['url'])

    prompt = f"""
    Analyze this website content and configure a customer support chatbot.
    Respond as valid JSON only. No markdown.

    {{
      "system_prompt": "2-3 sentences. Company name, what they do, tone.",
      "welcome_msg": "1 sentence, max 15 words.",
      "bot_name": "Usually [Company] Assistant",
      "suggested_qs": ["q1", "q2", "q3", "q4"],
      "fallback_msg": "Include support email if found in content."
    }}

    Website content:
    {summary}
    """

    config = json.loads(await llm_call(prompt, json_mode=True))
    await update_workspace_auto_config(workspace_id, config, color)
```

### Brand Color Detection
```python
async def extract_brand_color(url: str) -> str | None:
    html = await httpx_get(url)
    soup = BeautifulSoup(html, 'html.parser')
    # 1. meta theme-color
    meta = soup.find('meta', {'name': 'theme-color'})
    if meta:
        return meta.get('content')
    # 2. Scan CSS for most-frequent hex color in non-text elements
    # 3. Return None → use default #6366f1
    return None
```

### Page-Contextual Suggested Questions
```python
async def get_contextual_suggestions(workspace_id: str, page_url: str, workspace) -> list[str]:
    # Cache key: (workspace_id, page_url), TTL 1hr
    cached = suggestion_cache.get((workspace_id, page_url))
    if cached:
        return cached

    page_embedding = await embed_text(page_url)
    chunks = await similarity_search(workspace_id, page_embedding, limit=3)

    if not chunks:
        return workspace.suggested_qs or []

    questions = await generate_questions_from_chunks(chunks, page_url)
    suggestion_cache.set((workspace_id, page_url), questions, ttl=3600)
    return questions
```

---

## 14. BYOK (Bring Your Own API Key)

Available on **all tiers including free**. Self-hosters always use their own keys (no platform key needed).

**Supported providers:** OpenAI, Anthropic, Google

```python
from cryptography.fernet import Fernet

def encrypt_key(api_key: str) -> str:
    return Fernet(settings.ENCRYPTION_KEY.encode()).encrypt(api_key.encode()).decode()

def decrypt_key(encrypted: str) -> str:
    return Fernet(settings.ENCRYPTION_KEY.encode()).decrypt(encrypted.encode()).decode()

def get_llm_for_workspace(workspace) -> LLMClient:
    if workspace.byok_key_enc and workspace.byok_provider:
        key = decrypt_key(workspace.byok_key_enc)
        return LLMClient(provider=workspace.byok_provider, api_key=key)
    return LLMClient(provider='anthropic', api_key=settings.ANTHROPIC_API_KEY)
```

BYOK keys: never logged, never returned in API responses.

---

## 15. Security

### Prompt Injection Defense
Crawling arbitrary URLs and embedding content into LLM prompts is a real attack surface.
Applied to every chunk at crawl time — before embedding and before inserting into prompts.

```python
INJECTION_PATTERNS = [
    r'ignore (your|all|previous) (instructions?|system prompt|context)',
    r'you are now',
    r'new (persona|role|instructions?)',
    r'disregard (previous|above|all)',
    r'act as (if you are|a|an)',
    r'system prompt',
]

def sanitize_chunk(content: str) -> str:
    for pattern in INJECTION_PATTERNS:
        content = re.sub(
            r'[^.!?]*' + pattern + r'[^.!?]*[.!?]',
            '', content, flags=re.IGNORECASE
        )
    content = ''.join(c for c in content if c.isprintable() or c in '\n\t')
    return content.strip()
```

### Rate Limiting
10 requests/minute per `session_id` on `POST /api/chat`.

```python
from collections import defaultdict
from time import time

_rate_limits: dict[str, list[float]] = defaultdict(list)

def check_rate_limit(session_id: str, limit: int = 10, window: int = 60):
    now = time()
    timestamps = [t for t in _rate_limits[session_id] if now - t < window]
    if len(timestamps) >= limit:
        raise HTTPException(429, detail='Rate limit exceeded')
    timestamps.append(now)
    _rate_limits[session_id] = timestamps
```

In-memory for MVP — resets on restart. P1: Redis sliding window for multi-instance.

### CORS Policy
`POST /api/chat` and `GET /api/widget-config` have `Access-Control-Allow-Origin: *` **intentionally**.
The `api_key` is public by design (it's in the `<script>` tag on the host page). Open CORS is correct.
Allowed-domain restriction is a P1 feature. **Do NOT "fix" open CORS as a security bug.**

### GDPR
- `GET /api/gdpr/export` — full workspace data export as JSON
- `DELETE /api/gdpr/purge` — delete all conversations + messages
- `retention_days` on workspace — if set, background sweep deletes conversations older than N days

---

## 16. Outbound Webhooks

```python
async def dispatch_webhook(workspace_id: str, event: str, payload: dict):
    webhooks = await get_active_webhooks(workspace_id, event)
    for webhook in webhooks:
        body = json.dumps({
            "event": event,
            "workspace_id": str(workspace_id),
            "timestamp": datetime.utcnow().isoformat(),
            **payload
        })
        signature = hmac.new(
            webhook.secret.encode() if webhook.secret else b'',
            body.encode(), 'sha256'
        ).hexdigest()
        try:
            await httpx.post(webhook.url, content=body, headers={
                'Content-Type': 'application/json',
                'X-Pulse-Signature': f'sha256={signature}'
            }, timeout=5)
        except Exception:
            pass  # Fire and forget. P1: retry queue + delivery log.
```

Events dispatched:
- `conversation_started` — first message sent
- `conversation_ended` — session end signal received
- `email_captured` — visitor submits email
- `fallback_triggered` — confidence below threshold
- `thumbs_down` — visitor marks response unhelpful
- `lead_signal_detected` — intent classification detects presales signal

---

## 17. Admin Dashboard

**Stack:** Next.js 16 App Router + Auth.js v5 + Tailwind CSS + shadcn/ui

### Screens

#### Workspace Switcher (global)
Top-left dropdown listing all workspaces the user belongs to. "+ New workspace" creates one and enters onboarding.

#### Onboarding — Conversational Setup
See Section 11. Shown only when a workspace has no crawled content. Split-screen: setup chatbot (left) + live settings preview (right).

#### Home (Dashboard)
```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│ Convs today │ Msgs today  │ Unanswered  │ Top intent  │
│     24      │     89      │  🔴 12 new  │  Presales   │
└─────────────┴─────────────┴─────────────┴─────────────┘

Intent Distribution (this week)
  Presales ████████░░  43%
  Support  ██████░░░░  31%
  Navigate ███░░░░░░░  18%
  Complaint█░░░░░░░░░   8%

Recent Conversations (last 5)  [View all →]
```

#### Settings
Tabs: [Bot Config] [Appearance] [Knowledge Base] [BYOK] [Integrations] [Team] [Billing] [GDPR]

**Bot Config:** bot name, system prompt, welcome msg, fallback msg, suggested questions (4 chips)
**Appearance:** color picker, avatar upload, widget position, branding toggle (paid tiers)
**Knowledge Base:** URL + Retrain button, last crawled timestamp, page count
**BYOK:** provider dropdown (OpenAI / Anthropic / Google), API key field
**Integrations:** webhook config (URL + events), Calendly/Cal.com booking URL, embed guides (WordPress / Squarespace / Wix / HTML)
**Team:** member list, invite by email, role management
**Billing:** current plan, usage bar (convs this month / limit), upgrade/manage subscription
**GDPR:** export data, delete all conversations, configure retention policy

#### Conversations
Filter by intent, date range. List → transcript view with confidence indicators and source citations.

#### Unanswered Questions Feed
```
"What your visitors wanted to know — that your chatbot couldn't answer."

┌─────────────────────────────────────────────────────────┐
│ "Do you offer a free trial?"              Asked 23×     │
│ First seen 3 days ago · Last: 2h ago                    │
│ [View conversations] [Mark resolved] [Add to docs +]    │
└─────────────────────────────────────────────────────────┘
```

Feed query:
```sql
SELECT
    content AS question,
    COUNT(*) AS asked_count,
    MAX(created_at) AS last_seen,
    MIN(created_at) AS first_seen
FROM messages
WHERE workspace_id = $1
  AND role = 'user'
  AND is_unanswered = TRUE
GROUP BY content
ORDER BY asked_count DESC
LIMIT 50;
```

"Add to docs" → textarea → saves as document row → triggers re-embed.
"Mark resolved" → sets `is_unanswered = FALSE` on all matching user messages.
Phase 2: fuzzy dedup via pgvector — embed unanswered questions, cluster by similarity > 0.85 at render time.

---

## 18. Docker Compose (Self-Host)

```yaml
version: '3.9'
services:
  db:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: pulselite
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      retries: 5

  api:
    build: ./apps/api
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    command: uvicorn main:app --host 0.0.0.0 --port 8000

  web:
    build: ./apps/web
    env_file: .env
    ports:
      - "3000:3000"
    depends_on:
      - api

volumes:
  postgres_data:
```

Self-host in one command:
```bash
git clone https://github.com/[org]/pulse-lite
cd pulse-lite
cp .env.example .env
# Fill in: OPENAI_API_KEY, ANTHROPIC_API_KEY, AUTH_SECRET + SMTP
docker-compose up -d
```

---

## 19. Build Timeline — 14 Days

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1 | Repo setup, Docker Compose, PostgreSQL + pgvector, DB migrations (7 tables), tier config JSON | DB running, all tables created |
| 2 | Tiered crawler (httpx + Playwright fallback), sentence-aware chunking, HNSW embedding + insert | `POST /api/crawl` works on SSR and SPA sites |
| 3 | Auto-config service, brand color detection, page-contextual suggested questions | Crawl → auto-fills config + contextual chips |
| 4 | Chat pipeline: RAG, HNSW search, confidence routing, Claude Haiku SSE streaming | `POST /api/chat` streams |
| 5 | Fallback logic, `is_unanswered` on user message, rate limiting, prompt injection sanitization, booking intent | Gap detection + booking injection work |
| 6 | Vanilla JS widget: Shadow DOM, bubble, panel, streaming, sources, thumbs down, email capture, booking button | Widget production-ready |
| 7 | Widget: mobile full-screen, dark mode, session persistence, `visibilitychange` beacon, platform embed guides | Widget complete |
| 8 | Next.js 16 + Auth.js v5 setup, multi-workspace model, workspace switcher, home dashboard | Auth + workspace routing works |
| 9 | Conversational setup wizard: setup agent (Claude + tool use), split-screen layout, live preview updates | Onboarding works end-to-end |
| 10 | Settings screen (all tabs), conversations + transcript, unanswered feed, analytics, embed screen | All dashboard screens built |
| 11 | Intent classification (beacon + background sweep), webhook system, BYOK (OpenAI/Anthropic/Google) | Intelligence + integrations complete |
| 12 | CLOUD_MODE gating, Stripe integration (12 price IDs from tiers.json), usage middleware | Billing works |
| 13 | GDPR (export/purge/retention), team seats + invite flow, API access (authenticated endpoints) | Compliance + teams complete |
| 14 | Docker Compose polish, `.env.example`, README with GIF demo, smoke test all flows, AGPL headers | Ready to launch |

---

## 20. P0 / P1 / P2 Feature Flags

### P0 — Ships at Launch (Days 1–14)
- [x] Embeddable widget — 1 script tag, Shadow DOM
- [x] Streaming responses (SSE)
- [x] Website crawler — tiered (httpx + Playwright SPA fallback)
- [x] Sitemap ingestion
- [x] Auto-configuration (system prompt, welcome msg, color, FAQ chips)
- [x] Page-contextual suggested questions
- [x] RAG pipeline + HNSW vector search
- [x] Confidence-based fallback
- [x] Unanswered questions feed (auto-populated)
- [x] Add to docs from feed
- [x] Thumbs up/down
- [x] Intent classification — presales / support / navigation / complaint
- [x] Lead signal detection
- [x] Email capture on fallback
- [x] Booking intent detection + Calendly/Cal.com injection
- [x] Outbound webhooks (all events)
- [x] BYOK — OpenAI, Anthropic, Google (all tiers)
- [x] Conversational setup wizard (Claude + tool use, split-screen)
- [x] Multiple workspaces per account
- [x] Team seats + invite flow
- [x] Multi-workspace dashboard + switcher
- [x] Rate limiting (in-memory)
- [x] Prompt injection sanitization
- [x] GDPR — export, purge, configurable retention
- [x] Auth — magic link + Google OAuth (Auth.js v5)
- [x] Configurable tiers (tiers.json)
- [x] CLOUD_MODE gating (billing + usage only)
- [x] Stripe billing (12 price IDs)
- [x] Docker Compose self-host
- [x] API access (authenticated endpoints)
- [x] AGPL-3.0 license

### P1 — Month 2
- [ ] PDF / DOCX upload
- [ ] FAQ paste (plain text)
- [ ] Smart recrawl + change detection (APScheduler + content hash diff)
- [ ] Full analytics dashboard (intent chart, conv trends over time)
- [ ] Owner notification email on lead signal + email capture
- [ ] Allowed domains whitelist (CORS per workspace)
- [ ] Custom domain for hosted widget JS
- [ ] Rate limiting via Redis (multi-instance)
- [ ] Webhook delivery log + retry queue
- [ ] Custom API action mid-conversation
- [ ] Live search via Tavily integration

### P2 — Month 3+
- [ ] Gap clustering (fuzzy dedup + topic grouping via pgvector similarity)
- [ ] In-dashboard doc editor
- [ ] Human handoff / live agent escape hatch
- [ ] Notion / Google Drive connector
- [ ] A/B test system prompts
- [ ] Knowledge base versioning

### Full Pulse Only (not in Pulse Lite)
- ❌ BERTopic gap clustering
- ❌ Lead scoring (0–1 with session tracking)
- ❌ Exceptions queue + real-time routing
- ❌ Full inbox / helpdesk / multi-agent
- ❌ HubSpot / Salesforce CRM sync
- ❌ Slack team notifications
- ❌ Intercom importer
- ❌ SSO / SAML
- ❌ KB versioning + A/B testing
- ❌ Topic intelligence dashboard
- ❌ Sentiment trend analysis

---

## 21. Non-Negotiables

1. **`workspace_id` on every query** — no cross-tenant data leakage
2. **BYOK keys encrypted at rest (Fernet)** — never logged, never returned in API responses
3. **CLOUD_MODE=false is fully functional** — self-hosters get 100% of features, no limits
4. **Widget is zero-dependency** — never breaks host pages, works on any stack
5. **SSE streaming required** — no polling fallback
6. **`is_unanswered` always on the USER message** — both fallback detection and thumbs-down mark the user message, never the assistant. Feed query stays trivial.
7. **CORS is intentionally open on `/api/chat`** — `api_key` is public by design. Do NOT fix.
8. **Docker Compose works in one command** — tested on clean machine before launch
9. **AGPL-3.0 header in every source file**
10. **Tiers are config, not code** — adding/changing a tier requires only `tiers.json` + Stripe, zero code changes

---

## 22. Pre-Build Checklist

Resolve before Day 1:
- [ ] Domain confirmed? (`pulselite.com` or other)
- [ ] GitHub org name confirmed?
- [ ] SMTP provider? (Resend recommended)
- [ ] Stripe account live? Fill `stripe_price_ids` in `tiers.json`
- [ ] OpenAI + Anthropic API keys for platform use
- [ ] Google OAuth credentials (optional but P0)
- [ ] `ENCRYPTION_KEY` generated: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- [ ] `AUTH_SECRET` generated: `openssl rand -base64 32`
- [ ] Cloudflare account for widget CDN
- [ ] Clean Ubuntu VM available to validate Docker Compose self-host
