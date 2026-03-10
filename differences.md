# Pulse vs. Pulse Lite — Gap Analysis
**Date:** 2026-03-10 | **Reference:** `reference.md` (Pulse Lite spec) vs. current codebase

---

## Executive Summary

`reference.md` describes **Pulse Lite** — a dead-simple, self-hostable website chatbot targeting "paste URL → live in 60 seconds." The current codebase is a **full enterprise AI-native resolution platform** (full Pulse) — 5–10× more complex by design.

This document records every material difference between the two.

---

## 1. Tech Stack

| Layer | Lite Spec | Current Codebase | Delta |
|-------|-----------|-----------------|-------|
| Frontend | Next.js 16 + React 19.2 | Next.js 15.3.9 + React 19 | Version behind; no Turbopack stable / `"use cache"` |
| Backend | FastAPI (Python 3.11+) | FastAPI (Python 3.12) | Minor version ahead |
| Background Jobs | FastAPI `BackgroundTasks` + lifespan sweep | Celery + Redis (14 tasks + Beat scheduler) | **Explicitly excluded in spec** |
| Auth | Auth.js v5 (magic link + Google OAuth) | Custom JWT (access 30min + refresh 7d in Redis) + Google OAuth + OIDC SSO | No Auth.js; no magic link |
| LLM | Claude Haiku default; BYOK (OpenAI/Anthropic/Google) | Multi-model (OpenAI/Anthropic/Google) via OpenRouter BYOK | BYOK limited to OpenRouter only; no direct provider keys |
| Embedding | OpenAI `text-embedding-3-small` (1536d) | OpenAI embeddings + BM25 FTS | Enhanced with full-text search |
| Vector Search | pgvector HNSW | pgvector HNSW | Matches spec |
| BYOK Encryption | Fernet (per provider key) | Fernet used for SSO `client_secret`; BYOK stores raw OpenRouter key | Fernet not applied to BYOK |
| Rate Limiting | In-memory per `session_id` (Redis as P1) | Redis-backed via `slowapi` | More robust than spec |
| Cache | None at MVP | Redis | Over-spec |
| Analytics | None at MVP | BERTopic clustering, GPT-4o-mini analysis, sentiment, lead scoring | Explicitly excluded from Lite |
| Explicitly excluded by spec | Redis, Celery, Qdrant, BERTopic, multiple LLM UI, Kubernetes, SSO/SAML | All present in codebase | — |

---

## 2. Database Schema

### Lite Spec: 7 Tables
`workspaces`, `workspace_members`, `documents`, `chunks`, `conversations`, `messages`, `webhooks`

### Current Codebase: ~41 Model Classes

**Core (matches Lite):**
- `Chatbot` (≈ workspace bot config), `Document`, `Chunk`, `Conversation`, `Message`

**Additional (not in Lite spec):**

| Model | Purpose |
|-------|---------|
| `Workspace` | Org-level container (1 workspace → many chatbots) |
| `KnowledgeBase`, `ArticleCollection`, `Article` | Structured knowledge management |
| `Agent` | Multi-user per workspace |
| `Team`, `TeamMember` | Team routing |
| `Inbox` | Conversation routing |
| `WorkspaceMembership` | Role-based access |
| `WorkspaceWebhook` | Workspace-scoped outbound webhooks |
| `Contact`, `Company` | CRM-style contact tracking |
| `ContactEvent`, `DataAttribute`, `Segment` | Event-based contact intelligence |
| `Tag`, `ConversationTag` | Conversation categorization |
| `MessageFeedback` | Thumbs up/down (separate table vs. inline field in spec) |
| `Ticket` | Escalation tracking |
| `RetrievalLog` | RAG debug log |
| `GapEvent`, `GapCluster` | Unanswered question clustering |
| `IntelligenceSignal`, `TopicCluster` | BERTopic intelligence |
| `LeadScore`, `ConversationAnalysis` | Lead scoring + analysis |
| `AutonomousResolutionStats` | Primary KPI tracking |
| `ChatbotAction`, `ActionEvent` | AI action execution (Slack, Zapier, etc.) |
| `ApiKey` | Programmatic API access |
| `AuditLog` | Compliance audit trail |
| `IntegrationConfig` | OAuth tokens for Notion, Slack, Shopify, etc. |
| `CreditLedger` | Usage billing |
| `SSOConfig` | OIDC SSO per workspace |

**Key Structural Difference — Workspace Model:**

| Field | Lite Spec | Current |
|-------|-----------|---------|
| Bot config | Directly on `workspaces` (bot_name, system_prompt, color, etc.) | Moved to `Chatbot` model |
| Crawl state | On `workspaces` (crawl_status, pages_indexed, last_crawled_at) | On `Chatbot` |
| BYOK | `byok_provider` + `byok_key_enc` (Fernet) | `openrouter_api_key` + `allowed_models` |
| Usage tracking | `conv_count_month`, `conv_reset_at` | `plan_conversation_cap`, credit ledger |
| Bot relationship | 1 workspace = 1 bot | 1 workspace = many chatbots |

---

## 3. API Endpoints

### Lite Spec: ~24 Endpoints

**Public (widget):**
- `POST /api/chat` — SSE stream
- `POST /api/chat/feedback`
- `POST /api/chat/capture-email`
- `POST /api/chat/end-session`
- `GET /api/widget-config?key=&page=`

**Protected:**
- Workspaces CRUD + embed code (5)
- Team management (3)
- Crawl (start / status / delete) (3)
- Setup agent (1)
- Conversations + messages (2)
- Analytics summary (1)
- Unanswered feed + resolve + add-to-docs (3)
- BYOK set/delete (2)
- Webhooks CRUD (4)
- GDPR export/purge (2)
- Stripe billing (3, CLOUD_MODE only)

### Current Codebase: 26+ Routers / 100+ Endpoints

Routers present that are **not in Lite spec:**
- `actions` — AI action execution (Slack, Zapier, Calendly, Cal.com, custom button, web search)
- `audit` — Audit log access
- `completions` — Multi-LLM completion endpoint
- `dashboard` — Aggregated stats endpoint
- `exceptions` — Escalation/ticket management
- `gaps` — Gap clustering (BERTopic-based unanswered feed)
- `intelligence` — Sentiment, lead signals, topic clusters
- `invites` — Email-based workspace invitations
- `knowledge_bases` — KB management (collections, articles)
- `onboarding` — Step-tracking onboarding
- `share` — Public conversation sharing
- `sso (workspace_router)` — OIDC SSO config per workspace
- `sso (auth_router)` — Auth callback + discovery flows
- `two_fa` — TOTP 2FA setup/verify
- `instagram`, `messenger`, `whatsapp` — Meta channel webhooks
- `shopify_oauth` — Shopify OAuth + ScriptTag injection
- `slack_events` — Slack Events API (bot conversations)
- `oauth` — Shared OAuth callback (Notion, Slack, etc.)
- `credits` — Credit balance + recharge

---

## 4. Feature Parity Matrix

### Core Features

| Feature | Lite Spec | Current | Status |
|---------|-----------|---------|--------|
| Embeddable widget (Shadow DOM, 1 script tag) | ✅ Required | ✅ Present (`/widget/src/`) | **Implemented** |
| SSE streaming chat | ✅ Required | ✅ Present | **Implemented** |
| Website crawler (httpx + Playwright fallback) | ✅ Required | ❌ Absent | **MISSING** |
| Sitemap auto-discovery | ✅ Required | ❌ Absent | **MISSING** |
| Sentence-aware chunking (512 tok, 50 overlap) | ✅ Required | ✅ Present | **Implemented** |
| HNSW pgvector index | ✅ Required | ✅ Present | **Implemented** |
| Confidence-based fallback routing | ✅ 0.35 threshold | ✅ Configurable `confidence_threshold` (default 0.65) | **Implemented** (different default) |
| `is_unanswered` on user messages | ✅ Required | Partial — `GapEvent` table | **Different implementation** |
| Unanswered questions feed | ✅ `GET /api/unanswered` | ✅ `gaps` router (BERTopic-clustered) | **Different implementation** |
| Thumbs up/down feedback | ✅ Inline on message | ✅ Separate `MessageFeedback` table | **Implemented** (different schema) |
| Email capture on fallback | ✅ Inline widget form | ✅ Lead capture form | **Implemented** |
| Rate limiting | ✅ In-memory, 10/min per session | ✅ Redis `slowapi` | **Implemented** (enhanced) |
| Prompt injection sanitization | ✅ Required | ✅ Present (sanitize in ingestion extractors) | **Implemented** |
| GDPR export/purge | ✅ Required | ✅ Present | **Implemented** |
| Multi-workspace per account | ✅ Required | ✅ Present | **Implemented** |
| Team seats + invite flow | ✅ Required | ✅ Present | **Implemented** |
| Docker Compose self-host | ✅ Required | ✅ Present | **Implemented** |

### Setup & Onboarding

| Feature | Lite Spec | Current | Status |
|---------|-----------|---------|--------|
| Conversational setup wizard (Claude tool-use) | ✅ Core "wow" moment | ❌ Step-tracking form only | **MISSING** |
| Auto-configuration from crawled content (bot_name, welcome_msg, FAQ chips, system_prompt, color) | ✅ Required — `autoconfig.py` | ❌ Not found | **MISSING** |
| Brand color detection from HTML/meta theme-color | ✅ Required | ❌ Not found | **MISSING** |
| Embed code generation endpoint | ✅ `GET /api/workspaces/{id}/embed-code` | ❌ Not found | **MISSING** |
| Setup agent tool-use (crawl_website, update_workspace, get_embed_code) | ✅ Required | ❌ Not implemented | **MISSING** |

### Intelligence

| Feature | Lite Spec | Current | Status |
|---------|-----------|---------|--------|
| Intent classification (presales / support / navigation / complaint / other) | ✅ Required (async, post-conv) | ❌ Not implemented as described | **MISSING** |
| `has_lead_signal` detection (pricing, competitor, trial questions) | ✅ Required | ✅ `LeadScore` model, `intelligence_service.py` | **Different implementation** |
| Booking intent detection (`BOOKING_SIGNALS` list) | ✅ Required | ❌ Not found | **MISSING** |
| Page-contextual suggested questions (per page_url, cached 1hr) | ✅ Required | ❌ Static `suggested_qs` only | **MISSING** |
| Intent classification background sweep (lifespan, every 10min) | ✅ Required | ❌ Celery beat tasks, different purpose | **MISSING** |

### Auth

| Feature | Lite Spec | Current | Status |
|---------|-----------|---------|--------|
| Auth.js v5 | ✅ Required | ❌ Custom JWT | **MISSING** |
| Magic link email auth | ✅ Required | ❌ Not implemented | **MISSING** |
| Google OAuth | ✅ Required | ✅ Present | **Implemented** |
| OIDC SSO (Okta, Entra, etc.) | ❌ Explicitly excluded | ✅ Present (4 providers) | Over-spec |
| 2FA (TOTP) | ❌ Not in spec | ✅ Present | Over-spec |

### BYOK & LLM

| Feature | Lite Spec | Current | Status |
|---------|-----------|---------|--------|
| BYOK: OpenAI / Anthropic / Google (direct) | ✅ All three, Fernet-encrypted | ✅ OpenRouter only (not direct providers) | **PARTIAL** |
| Fernet encryption for BYOK keys | ✅ Required | ❌ Fernet used for SSO secrets; BYOK stores plaintext OpenRouter key | **MISSING** |
| Default LLM: Claude Haiku | ✅ Required | ✅ Anthropic default via OpenRouter | **Implemented** |
| Multiple LLM picker UI | ❌ Explicitly excluded | ✅ Full model picker | Over-spec |

### Configuration & Billing

| Feature | Lite Spec | Current | Status |
|---------|-----------|---------|--------|
| Data-driven tiers via `config/tiers.json` | ✅ Required — zero-code tier changes | ❌ Hardcoded in billing service | **MISSING** |
| BYOK discount (50% off paid tier) | ✅ Specified | ❌ Not implemented | **MISSING** |
| `CLOUD_MODE` flag (single env var gates billing/limits only) | ✅ Required | ✅ Partially present | **Partial** |
| Stripe billing (12 price IDs, CLOUD_MODE only) | ✅ Required | ✅ Present | **Implemented** |
| Plan usage enforcement (conv_count_month) | ✅ Required | ✅ Credit ledger system | **Different implementation** |

---

## 5. Widget Differences

### Lite Spec
- Vanilla JS (no framework), ~5kb gzipped
- Shadow DOM (closed mode)
- Page-contextual chip questions (fetched on load with `page` param)
- `visibilitychange` → `navigator.sendBeacon` for session end + intent classification trigger
- Booking button rendered when assistant response contains `booking_url`
- Email capture inline when `is_fallback=true`
- Mobile full-screen overlay < 480px
- Dark mode via `prefers-color-scheme`

### Current Widget
- TypeScript (compiled), Shadow DOM ✅
- Static `suggested_qs` chips — **no page-contextual generation** ❌
- `visibilitychange` beacon — **not found** ❌
- Booking button — **not found** ❌
- Email capture / lead form ✅
- Mobile responsive ✅
- Dark mode ✅
- Voice/dictation input (added in session 5 — not in spec) ✅ (over-spec)

---

## 6. File Structure Comparison

### Lite Spec (simplified monorepo)
```
pulse-lite/
├── apps/web/          # Next.js dashboard + landing
├── apps/api/          # FastAPI backend
│   ├── routers/       # chat, setup, crawl, workspaces, conversations, analytics, webhooks
│   └── services/      # crawler, embedder, retriever, llm, autoconfig, intent, webhook_dispatcher
├── widget/            # Vanilla JS embeddable widget
└── config/tiers.json
```

### Current Codebase
```
pulse/
├── frontend/          # Next.js 15 (31 pages)
├── backend/
│   ├── app/api/v1/    # 26 route handlers
│   ├── app/services/  # 20+ service modules
│   ├── app/models/    # 13 model files, ~41 classes
│   └── app/workers/   # 14 Celery tasks
├── widget/            # TypeScript widget
└── infra/             # Docker / k8s config
```

**Key missing service files (from Lite spec):**
- `backend/app/services/crawler.py` — web crawler
- `backend/app/services/autoconfig.py` — auto-configuration
- `backend/app/services/intent.py` — intent classification
- `backend/app/routers/setup.py` — conversational setup agent
- `config/tiers.json` — data-driven tier config

---

## 7. Non-Negotiables in Lite Spec — Compliance Check

| Non-Negotiable | Lite Spec Requirement | Current Status |
|---------------|----------------------|----------------|
| `workspace_id` on every query | No cross-tenant leakage | ✅ Enforced via `Depends(get_workspace)` |
| BYOK keys encrypted at rest (Fernet) | Never logged, never returned | ❌ OpenRouter key stored without Fernet |
| `CLOUD_MODE=false` fully functional | Self-hosters get 100% features | ✅ Partial |
| Widget is zero-dependency | Never breaks host pages | ✅ Shadow DOM, no framework deps |
| SSE streaming required | No polling fallback | ✅ Present |
| `is_unanswered` always on USER message | Feed query stays trivial | ❌ Implemented differently via GapEvent |
| CORS intentionally open on `/api/chat` | `api_key` is public | ✅ Open CORS on widget routes |
| Docker Compose works in one command | Tested on clean machine | ✅ Present |
| AGPL-3.0 header in every source file | License compliance | ❌ Not present |
| Tiers are config, not code | `tiers.json` only | ❌ Hardcoded |

---

## 8. Features in Current Codebase Explicitly Excluded from Lite Spec

| Feature | Spec Says | Current Has |
|---------|-----------|------------|
| Redis | ❌ Excluded | ✅ Present (rate limiting, JWT, caching, Celery) |
| Celery | ❌ Excluded | ✅ 14 tasks + Beat scheduler |
| BERTopic | ❌ Excluded | ✅ Gap clustering + topic intelligence |
| Multiple LLM picker UI | ❌ Excluded | ✅ Full model picker per chatbot |
| Kubernetes | ❌ Excluded | ✅ Infra configs present |
| SSO/SAML | ❌ Excluded | ✅ OIDC SSO (4 providers) |
| Qdrant | ❌ Excluded | ✅ Not present (pgvector used — correct) |
| Intercom compat | ❌ Excluded | Partial (webhook field references) |
| Lead scoring pipeline | ❌ Excluded | ✅ `LeadScore` model + scoring service |

---

## 9. Summary: What to Build for Pulse Lite

If shipping Pulse Lite as described in `reference.md`, the following are required and absent:

### P0 — Core Promise Blockers
Without these, the "paste URL → live in 60 seconds" promise cannot be delivered:

1. **Web Crawler** — `backend/app/services/crawler.py`
   - Tiered fetch: httpx fast path (< 500 chars → Playwright fallback)
   - Sitemap discovery (`/sitemap.xml` → BFS fallback)
   - BeautifulSoup content extraction + sanitization
   - Sentence-aware chunking (512 tokens, 50 overlap)

2. **Auto-Configuration Service** — `backend/app/services/autoconfig.py`
   - Post-crawl: LLM call to generate `bot_name`, `welcome_msg`, `system_prompt`, `suggested_qs`, `fallback_msg`
   - Brand color extraction from `meta[name=theme-color]` + CSS scan

3. **Conversational Setup Wizard** — `backend/app/routers/setup.py` + frontend split-screen page
   - Claude with tool use: `crawl_website`, `update_workspace`, `get_embed_code`
   - SSE stream emits `tool_result` events → frontend updates live preview panel

### P1 — Intelligence
4. **Intent Classification** — `backend/app/services/intent.py`
   - Post-conversation async: `presales | support | navigation | complaint | other`
   - `has_lead_signal` detection
   - Triggered via `POST /api/chat/end-session` (widget beacon) + lifespan sweep

5. **Booking Intent Detection** — inline in chat pipeline
   - Keyword match against `BOOKING_SIGNALS` list
   - Inject `booking_url` into system prompt when detected

6. **Page-Contextual Suggested Questions** — widget config + cache
   - `page` param on `GET /api/widget-config` → vector search → LLM generates 3–4 chips
   - 1hr cache per `(workspace_id, page_url)`

### P2 — Configuration
7. **Data-Driven Tiers** — `config/tiers.json`
   - Replace hardcoded billing limits with JSON config
   - `BYOK discount = 50%` rule

8. **Fernet BYOK Encryption**
   - Apply Fernet encryption to OpenRouter key at rest
   - Extend to direct OpenAI/Anthropic/Google provider keys

9. **Auth.js v5 + Magic Link Email**
   - Replace custom JWT with Auth.js adapter
   - SMTP magic link flow

### P3 — Polish
10. **Embed code generation endpoint** — `GET /api/workspaces/{id}/embed-code`
11. **Widget `visibilitychange` beacon** — session end → intent classification
12. **AGPL-3.0 headers** in all source files
13. **Upgrade Next.js 15 → 16** (Turbopack stable + `"use cache"`)

---

## 10. What Does NOT Need to Change

The following aspects of the current codebase **already satisfy** the Lite spec:

- pgvector HNSW index (matches spec exactly)
- Shadow DOM widget architecture
- Confidence-based fallback routing (different threshold but same logic)
- Outbound webhooks with HMAC signing
- GDPR export/purge endpoints
- Multi-workspace per account
- Team seats + invite flow
- Docker Compose self-host
- Open CORS on widget endpoints
- Rate limiting (current is better than spec)
- Prompt injection sanitization in ingestion pipeline
- Stripe billing (present, CLOUD_MODE gated)
