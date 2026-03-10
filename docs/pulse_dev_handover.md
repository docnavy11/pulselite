# Pulse — Developer Handover Document
## Product Requirements & Functional Specification
### Version 1.0 — March 2026

---

## Table of Contents

0. [Critical Context — Read First](#0-critical-context)
1. [Non-Functional Requirements](#1-non-functional-requirements)
2. [Tech Stack](#2-tech-stack)
3. [Data Model](#3-data-model)
4. [Phase 1 MVP Scope](#4-phase-1-mvp-scope)
5. [Module Specifications](#5-module-specifications)
   - 5.1 RAG Pipeline & Autonomous Resolution Engine
   - 5.2 Living Knowledge Base
   - 5.3 Exceptions Queue
   - 5.4 Intelligence Layer (7 modules)
   - 5.5 Deployment & Widget
   - 5.6 Integrations
6. [Phase 2 Overview](#6-phase-2-overview)
7. [Explicitly Deferred](#7-explicitly-deferred)

---

## 0. Critical Context — Read First {#0-critical-context}

### What Pulse Is

Pulse is an **AI-native autonomous resolution platform** — a Chatbase/Intercom alternative built around the principle that AI should resolve support conversations autonomously, with humans as the exception, not the rule.

This is **not** a traditional helpdesk with AI bolted on. The inbox is a fallback. The intelligence dashboard is the primary product.

### The Primary KPI: Autonomous Resolution Rate

Every product decision flows from one metric: **what % of conversations does the AI fully resolve without human intervention?**

This metric is surfaced on the dashboard from day one. It is the product's proof of ROI.

### The Build Philosophy

> Autonomous resolution core first. Human fallback UI second. Legacy parity features deferred.

- **Phase 1**: RAG engine + intelligence layer + exceptions queue (minimal human fallback)
- **Phase 2**: Advanced intelligence + platform ecosystem
- **Phase 3**: Full inbox, traditional helpdesk parity features

### The Trojan Horse GTM

Pulse enters as a **Chatbase alternative** (simple chatbot builder — low barrier). The intelligence layer is the upsell and retention mechanism. Once customers see documentation gap reports, lead scores, and feature request clusters from their own conversations, they cannot go back to a dumb chatbot.

### Positioning

| Competitor | Pulse vs. Them |
|------------|----------------|
| Chatbase | + Intelligence layer, + BYOK, + living KB, + lead scoring |
| Intercom | Fraction of cost, AI-first architecture, no bloat |
| Zendesk | No legacy complexity, built for AI-native resolution |
| Drift | Unified pre+post-sales, not just lead capture |

### Target Customers

**Primary ICP**: Growth-stage B2B SaaS (20–500 employees, active support + sales motion)
**Secondary ICP**: Digital agencies building for clients
**Tertiary ICP**: SMBs with active sales + support needs

---

## 1. Non-Functional Requirements {#1-non-functional-requirements}

### 1.1 Multi-Tenancy

- **Model**: Multi-tenant SaaS. Each customer is a **workspace**. All data is workspace-scoped.
- **Isolation**: Logical isolation (row-level, workspace_id on all tables). No physical DB separation required at launch.
- **Architecture**: Must be designed to scale to physical isolation (per-tenant schemas or DBs) for future enterprise tier — do not hard-code assumptions that prevent this migration.
- **Cross-tenant data access**: Must be architecturally impossible. Workspace data is never accessible to other workspaces.

### 1.2 Authentication & Access Control

- **Login methods supported**:
  - Email + password
  - Google OAuth
  - SSO / SAML (required — even if hidden behind a higher tier)
- **RBAC**: Full role-based access control required. Roles are workspace-scoped. Specific role definitions TBD (at minimum: Owner, Admin, Member). RBAC features may be **hidden/gated** behind certain subscription tiers but must be built into the architecture from day one.
- **Invite flow**: To be defined — design for email-based workspace invitations as the default.
- **Session management**: Secure token-based sessions. Specifics (JWT, refresh strategy) at dev team discretion.

### 1.3 BYOK (Bring Your Own API Key) + Credits

- **BYOK is optional**, not mandatory. Two modes must coexist:
  - **BYOK mode**: User provides their own LLM API key(s). Platform fee only, no per-token charge.
  - **Credits mode**: User does not provide a key. Platform provides LLM access via a credits system (purchased or subscription-allocated).
- **Supported BYOK providers**: As many as possible. Minimum: OpenAI, Anthropic, Google (Gemini), Azure OpenAI. Architecture should make adding providers trivial.
- **Key storage**: API keys stored per-workspace, encrypted at rest. Never exposed in API responses or logs.
- **Usage visibility (BYOK)**: Users in BYOK mode see their own API usage/cost breakdown in the dashboard (model calls, estimated cost).
- **Credits visibility**: Users in credits mode see their credit balance and consumption.

### 1.4 White-Labeling

- **Required in Phase 1.**
- Customers can brand:
  - The chat widget (logo, colors, name, avatar)
  - The chatbot persona (name, tone)
- Dashboard white-labeling (agency reseller use case): Phase 2.

### 1.5 Performance & Scale

- **No specific concurrent user targets defined at launch.** Build the right architecture for horizontal scaling.
- **Chat response time**: Minimize end-to-end latency. Stream responses where possible (SSE or WebSocket). Perceived speed is a product quality signal.
- **Background jobs**: Intelligence processing (topic clustering, gap detection, post-conversation analysis) runs async — never blocks the chat experience.
- **Architecture must support**: Horizontal scaling of API layer, independent scaling of background workers, queue-based job processing.

### 1.6 Compliance & Security

- **GDPR**: Required from day one. EU customers expected at launch.
  - Data processing agreements
  - Right to deletion (workspace + contact level)
  - Data export capability
  - Cookie consent on widget
- **SOC 2**: Target compliance. Design with SOC 2 controls in mind (audit logging, access controls, encryption).
- **Encryption**: Data encrypted at rest and in transit.
- **Audit logging**: All admin actions and data access logged.

### 1.7 Data Retention

- **Configurable per workspace.** No platform-wide fixed retention period.
- Workspaces can define retention policies for: conversations, messages, contact events, intelligence logs.
- Automated purging of data beyond retention window.
- Default retention period TBD (suggest: 2 years as default).

### 1.8 Billing & Subscription Tiers

- **Tier structure**: To be defined. Architecture must support **configurable feature flags per tier**.
- Features (RBAC, SSO, white-labeling, BYOK, integrations, intelligence modules) must be implementable as tier-gated without code changes — config/flag driven.
- **Free trial**: Likely yes. Design for trial period with conversion to paid.
- **Freemium tier**: Possibly. Design for it.
- Billing integration (Stripe or equivalent) is a Phase 1 requirement.

---

## 2. Tech Stack {#2-tech-stack}

> The following stack was decided based on research. Dev team may propose alternatives with rationale.

| Layer | Technology | Rationale |
|-------|-----------|----------|
| Frontend | Next.js 14 + TypeScript + Tailwind | Modern, fast, excellent DX |
| Widget | Vanilla JS + CSS (no framework) | Embeds on any site without conflicts |
| Backend API | FastAPI (Python) | Async support, excellent AI library ecosystem |
| LLM Orchestration | LangChain or custom RAG pipeline | Flexibility across models |
| Vector DB | Qdrant (self-hosted) or pgvector | Production-grade vector search |
| Relational DB | PostgreSQL | ACID compliance for conversation/lead data |
| Background Jobs | Celery + Redis | Proven async job processing |
| Embedding Model | text-embedding-3-small (OpenAI) | Cost-efficient, high quality |
| Topic Clustering | BERTopic + LLM labeling | Zero-setup dynamic topic modeling |
| Post-conv Analysis | GPT-4o-mini or Claude Haiku | Fast, cheap, structured JSON output |
| Infrastructure | Docker + Kubernetes | Scalable, multi-tenant |
| CDN | Cloudflare | Widget delivery + edge caching |

---

## 3. Data Model {#3-data-model}

> Full data model: `/a0/usr/workdir/pulse_data_model.md`
> Validated against live APIs: Intercom, Chatwoot, Chatbase, Crisp, Zendesk

### 3.1 Summary — 27 Tables across 6 domains

| Domain | Tables |
|--------|--------|
| **Organizational** | workspaces, agents, teams, inboxes |
| **Contact & Identity** | contacts, companies, contact_events, data_attributes, segments |
| **Conversation** | conversations, messages, tags, tickets |
| **Knowledge Base** | chatbots, knowledge_bases, documents, articles |
| **AI-Native Intelligence** | retrieval_logs, gap_events, gap_clusters, intelligence_signals, topic_clusters, lead_scores, conversation_analysis, autonomous_resolution_stats |
| **Compatibility** | Cross-platform status mapping, author type mapping, timestamp normalization |

### 3.2 Critical Architectural Notes

- **workspace_id is on every table** — all queries are workspace-scoped, all indexes include workspace_id
- **retrieval_logs is the foundational AI-native table** — every RAG call logs confidence score, source, latency. Powers gap detection, resolution stats, and all intelligence modules
- **autonomous_resolution_stats** — tracks the primary KPI (resolution rate) over time per chatbot and workspace
- **Intercom compatibility layer** is built into the schema (status mappings, author types, timestamp normalization) to enable data import from Intercom
- **Timestamp normalization**: 4 different formats exist in the wild — the data model normalizes all to UTC ISO 8601. See section 8 of data model doc.
- **10 Critical Intercom API Gotchas** documented in data model section 9 — engineering must read before building the import layer

---

## 4. Phase 1 MVP Scope {#4-phase-1-mvp-scope}

### ✅ In Scope — Phase 1 (Must Build)

| Module | Description |
|--------|-------------|
| RAG Pipeline & Autonomous Resolution Engine | The core product |
| Living Knowledge Base | AI-maintained, gap-driven |
| Exceptions Queue | Minimal human fallback (NOT a full inbox) |
| Intelligence Layer — all 7 modules (initiated) | This IS the product |
| Deployment & Widget | Embeddable chat widget + web snippet |
| Core Integrations | Slack (escalation alerts), email (escalation), CRM push (lead scores) |
| BYOK + Credits system | Dual LLM access model |
| White-labeling | Widget + chatbot persona |
| Auth (all methods) | Email, Google OAuth, SSO/SAML |
| RBAC | Full RBAC (tier-gated in UI) |
| GDPR compliance | Deletion, export, consent |
| Billing integration | Stripe, tier-based feature flags |

### 🚀 Phase 2 (Should Build — After Phase 1)

- Advanced KB features (multi-language, version history)
- Advanced intelligence depth (all 7 modules go deeper)
- More integrations (HubSpot bi-directional, Pipedrive, Jira/Linear, Calendly, Stripe sidebar)
- Dashboard white-labeling (agency reseller)
- Intercom data importer (OAuth-based, 7-phase)
- API access for customers (public REST API)
- Zapier/Make native integration

### ⏭️ Explicitly Deferred — Phase 3+

- Full shared inbox (traditional helpdesk)
- CSAT surveys (Phase 1 infers sentiment from conversation)
- Complex routing rules UI (Phase 1 uses intent-based routing)
- Live chat with human agents as primary flow
- Phone/voice support
- Full Intercom API compatibility layer (drop-in replacement)

---

## 5. Module Specifications {#5-module-specifications}

---

### 5.1 RAG Pipeline & Autonomous Resolution Engine

> **This is the core product.** Everything else depends on it working well.

#### What It Does
The engine receives a user message, retrieves relevant knowledge from the KB using hybrid retrieval, generates a response using the configured LLM, scores confidence, and decides to either resolve (deliver answer) or escalate (route to exceptions queue).

#### Functional Requirements

| Requirement | Detail |
|-------------|--------|
| **Multi-source KB ingestion** | URLs (with crawling), PDFs, DOCX, TXT, Notion, CSV, Q&A pairs |
| **Content-aware chunking** | Semantic + markdown-aware + code-aware chunking (not fixed-size) |
| **Hybrid retrieval** | Dense (vector) + sparse (BM25) combined — measurably better recall than vector-only |
| **AI Confidence Score** | Every RAG call scored 0–1. Logged to retrieval_logs every time. Non-negotiable. |
| **Cross-encoder reranking** | Top-k candidates reranked before generation |
| **Autonomous resolution loop** | Bot attempts answer → confidence check → resolve or escalate |
| **Source citations** | Every response cites the source article/document |
| **Auto-sync / re-crawl** | Re-ingests sources on schedule (daily/weekly) or on-demand |
| **Multi-LLM support** | GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro minimum |
| **BYOK** | Users provide own API key; platform fee only. See Section 1.3. |
| **Bot persona & instructions** | Custom name, personality, tone, off-topic restrictions |
| **Conversation memory** | Within-session memory; optional persistent cross-session |
| **Streaming responses** | Stream tokens to widget for perceived speed |

#### Confidence Threshold Logic

- **High confidence** (threshold configurable per chatbot, default ~0.7): Auto-resolve, deliver answer
- **Low confidence**: Escalate to exceptions queue with reason code
- Threshold is configurable per chatbot by the workspace admin

#### Escalation Taxonomy

When escalating, the engine tags the reason:
- `low_confidence` — RAG score below threshold
- `negative_sentiment` — Detected anger/frustration in message
- `high_value` — Lead score above threshold
- `compliance` — Topic flagged as requiring human
- `explicit_request` — User explicitly asked for a human

---

### 5.2 Living Knowledge Base

> The KB is AI-maintained. It detects its own gaps and proposes fixes.

#### What It Does
Tracks low-confidence retrievals, clusters them into named gap topics, drafts KB articles to fill those gaps, and presents them for human approval. Approved articles are immediately re-indexed.

#### Functional Requirements

| Requirement | Detail |
|-------------|--------|
| **Documentation Debt tracker** | Every low-confidence retrieval logged as a gap_event |
| **Gap clustering** | Clusters similar gap events into named topics (weekly job) |
| **Auto-draft article from gap** | LLM drafts a KB article for each gap cluster |
| **Human approval queue** | Review AI-drafted article: approve / edit / reject |
| **KB article management UI** | View, edit, delete, add individual KB articles |
| **Re-index on approval** | Approved article immediately re-indexed into vector store |
| **Knowledge Velocity metric** | Weekly KB improvement rate: gaps closed vs. new gaps opened |

#### Knowledge Base Structure

- A workspace can have multiple **chatbots**
- Each chatbot has one or more **knowledge_bases**
- A knowledge base contains **documents** (ingestion sources) and **articles** (individual KB entries)
- Articles can be: AI-drafted (pending approval), human-written, or imported

---

### 5.3 Exceptions Queue

> This is the human interface. It is NOT a traditional inbox. Only AI-escalated conversations appear here.

#### What It Does
Shows only conversations the AI could not resolve, with full context, escalation reason, confidence timeline, and suggested next action.

#### Functional Requirements

| Requirement | Detail |
|-------------|--------|
| **Escalation queue view** | Only AI-escalated conversations, with reason + confidence score |
| **Escalation reason tag** | Why AI escalated: confidence / sentiment / value / compliance / explicit |
| **Full conversation context** | Entire conversation + confidence score timeline + customer data |
| **Suggested action** | AI recommends next action (refund / escalate to CS / send doc link) |
| **Basic reply interface** | Human can respond; conversation marked resolved |
| **Slack/email escalation push** | Notify team when escalation arrives (configurable) |
| **Escalation resolution logging** | How human resolved it — feeds AI improvement cycle |

#### What This Is NOT
- Not a full shared inbox
- Not a team collaboration tool
- Not a ticketing system
- Full inbox is Phase 3

---

### 5.4 Intelligence Layer — 7 Modules

> The intelligence layer is the primary reason Pulse exists and the core differentiator. All 7 modules are initiated in Phase 1.
> Full research: `/a0/usr/workdir/intelligence_layer_research.md`

#### Shared Infrastructure

- **Post-conversation LLM analysis**: Async job runs after every conversation ends. Extracts ~15 structured fields per conversation (sentiment, topics, intent, lead signals, feature requests, competitive mentions, etc.). Stored in `conversation_analysis` table. Powers all 7 modules downstream.
- **Proactive push**: All intelligence modules can push alerts to Slack/email when anomalies are detected. Weekly digest email summarizing all intelligence.

---

#### 5.4.1 Lead Intelligence

**What it does**: Scores every conversation for sales lead potential in real-time. Pushes high-scoring leads to CRM.

| Requirement | Detail |
|-------------|--------|
| **Real-time lead scoring** | Score updated per message during conversation (0–100) |
| **Signal taxonomy** | Detects: pricing questions, competitor mentions, company size signals, urgency language, decision-maker indicators, integration questions, trial/demo requests |
| **Score thresholds** | Configurable: alert threshold, CRM push threshold |
| **CRM push** | Auto-push lead data to connected CRM at threshold |
| **Lead intelligence dashboard** | Sorted lead feed with scores, signals, conversation excerpts |
| **Post-conversation full scoring** | Full LLM analysis run after conversation ends for complete scoring |

---

#### 5.4.2 Documentation Gap Detection

**What it does**: Automatically identifies what's missing from the knowledge base based on real user questions the AI couldn't answer.

| Requirement | Detail |
|-------------|--------|
| **Gap event logging** | Every low-confidence retrieval = gap_event with query, confidence, chatbot |
| **Weekly gap clustering** | Similar gaps grouped into named clusters with volume |
| **Gap report** | Weekly report: top gap clusters, frequency, suggested KB articles |
| **Auto-draft KB article** | LLM drafts article for each cluster → human approval queue |
| **Self-improvement loop** | Gaps → drafts → approvals → re-index → resolution rate improves |
| **Knowledge Velocity metric** | Tracks rate of KB improvement over time |

---

#### 5.4.3 Functional Gap Detection (Feature Requests)

**What it does**: Extracts and clusters product feature requests from support conversations. Pushes clusters to product management tools.

| Requirement | Detail |
|-------------|--------|
| **Feature request extraction** | Post-conversation analysis extracts feature requests with verbatim quotes |
| **Weekly clustering** | Similar requests grouped, named, and ranked by frequency |
| **Feature request feed** | Dashboard view: clusters with volume, trend, example quotes |
| **Push to PM tools** | Configurable push to Jira, Linear (Phase 1: at least one of these) |
| **Trend detection** | Alert when a new feature request cluster surges |

---

#### 5.4.4 Topic Intelligence

**What it does**: Zero-setup topic analytics. Automatically clusters all conversation topics without any configuration.

| Requirement | Detail |
|-------------|--------|
| **Autonomous topic clustering** | Nightly job clusters all conversation topics using NLP |
| **Zero configuration** | No manual tagging or category setup required |
| **Topic volume + trend** | Each cluster shows: volume, trend (up/down), example conversations |
| **Topic intelligence dashboard** | Visual overview of what users are talking about |
| **Anomaly alerts** | Alert when a topic spikes unexpectedly |

---

#### 5.4.5 Sentiment Intelligence

**What it does**: Tracks sentiment trends across conversations over time. Alerts on deterioration.

| Requirement | Detail |
|-------------|--------|
| **Per-conversation sentiment** | Sentiment scored per conversation (not just per message) |
| **Trend tracking** | Sentiment trends over time, per chatbot, per topic |
| **Alert conditions** | Alert when sentiment drops below threshold or deteriorates rapidly |
| **Sentiment dashboard** | Time-series view of sentiment with drill-down to conversations |
| **Segment-level sentiment** | Sentiment by customer segment / company / contact |

---

#### 5.4.6 Competitive Intelligence

**What it does**: Extracts competitor mentions from conversations. Surfaces competitive signals.

| Requirement | Detail |
|-------------|--------|
| **Competitor mention extraction** | Post-conversation analysis detects competitor mentions |
| **Competitive signal feed** | Dashboard: which competitors mentioned, frequency, context |
| **Competitor configuration** | Workspace defines their competitor list |
| **Trend alerts** | Alert when a competitor mention frequency spikes |

---

#### 5.4.7 Autonomous Resolution Dashboard

**What it does**: The primary KPI dashboard. Shows the autonomous resolution rate prominently.

| Requirement | Detail |
|-------------|--------|
| **Resolution rate** | % conversations fully resolved by AI, displayed on dashboard homepage |
| **Trend** | Weekly resolution rate trend |
| **Breakdown** | Resolution rate by chatbot, by topic, by time period |
| **Escalation analysis** | Why conversations escalated — breakdown by escalation reason |
| **Impact of KB improvements** | Show how resolution rate changed after KB articles approved |

---

### 5.5 Deployment & Widget

#### Chat Widget (Embeddable)

| Requirement | Detail |
|-------------|--------|
| **Implementation** | Vanilla JS + CSS — no framework dependency, embeds on any site |
| **Installation** | Single script tag with chatbot ID |
| **Cross-origin** | Fully CORS-compatible, works on any domain |
| **Customization** | Logo, primary color, chatbot name, avatar, position (bottom-right/left), welcome message |
| **White-labeling** | Full brand customization (Phase 1) |
| **Streaming** | Streams response tokens for perceived speed |
| **Conversation persistence** | Optional — remember user across sessions (configurable) |
| **Mobile responsive** | Works on all screen sizes |
| **GDPR cookie consent** | Configurable consent banner before widget initializes |

#### Deployment Channels (Phase 1)

| Channel | Requirement |
|---------|-------------|
| **Embeddable widget** | JS snippet for any website |
| **Shareable link** | Standalone hosted chat URL per chatbot |
| **API access** | REST API to send/receive messages programmatically |

---

### 5.6 Integrations — Phase 1

| Integration | What's Required |
|-------------|----------------|
| **Slack** | Escalation alerts (new escalation → Slack message with context + link). Weekly intelligence digest to Slack channel. |
| **Email** | Escalation alerts via email. Weekly intelligence digest email. |
| **CRM push (lead scores)** | Push lead data (contact info, score, signals, conversation summary) to CRM when threshold hit. Phase 1: HubSpot at minimum. |
| **Jira or Linear** | Push feature request clusters to PM tool. Phase 1: at least one. |
| **Zapier/Make** | Via webhook compatibility — not a native integration, but webhook output should be structured for easy Zapier/Make use. |

---

## 6. Phase 2 Overview {#6-phase-2-overview}

Phase 2 deepens intelligence and builds the ecosystem:

- **Advanced KB**: Multi-language support, KB article versioning, public help center portal
- **Advanced Intelligence**: All 7 modules go deeper (more signals, more granular reporting, more automation)
- **Intercom data importer**: OAuth 2.0 flow, 7-phase import, rate-throttled at 800 req/min
- **Intercom API compatibility layer**: Drop-in replacement (single baseURL change = migrations work)
- **Extended integrations**: HubSpot bi-directional, Pipedrive, Calendly, Stripe sidebar, Segment
- **Customer-facing API**: Public REST API for workspace management, conversations, contacts
- **Dashboard white-labeling**: Agency reseller use case
- **Advanced BYOK**: Usage analytics, cost forecasting

---

## 7. Explicitly Deferred {#7-explicitly-deferred}

Do not build these in Phase 1. Do not design Phase 1 in a way that blocks them.

| Feature | Deferred To |
|---------|-------------|
| Full shared inbox (traditional helpdesk) | Phase 3 |
| CSAT surveys | Phase 3 (sentiment inferred from conversation in Phase 1) |
| Routing rules UI (complex) | Phase 3 (intent-based routing in Phase 1) |
| Live human agent as primary flow | Phase 3 |
| Phone / voice support | Phase 4+ |
| Full Intercom API compatibility | Phase 2 |
| Enterprise physical tenant isolation | Future enterprise tier |
| On-premise deployment | Future |
| SLA management | Phase 3 |
| Customer portal (self-service) | Phase 3 |

---

## 8. Supporting Documents

| Document | Path | Description |
|----------|------|-------------|
| Product Blueprint | `/a0/usr/workdir/PRODUCT_BLUEPRINT.md` | Full product vision, architecture, module specs, positioning |
| Data Model | `/a0/usr/workdir/pulse_data_model.md` | 27-table schema, validated against Intercom/Chatbase/Chatwoot |
| Intelligence Layer Research | `/a0/usr/workdir/intelligence_layer_research.md` | Deep research on all 7 intelligence modules |
| RAG Chunking Research | `/a0/usr/workdir/rag_chunking_research.md` | RAG pipeline strategy, chunking approaches, gap detection |
| Chatbase Feature List | `/a0/usr/workdir/chatbase_full_feature_list.md` | 320 features, 23 sections — primary competitor reference |
| Intercom Research | `/a0/usr/workdir/intercom_research.md` | Intercom deep-dive, API gotchas, pricing context |
| Intercom Full Feature List | `/a0/usr/workdir/intercom_full_feature_list.md` | Full Intercom feature reference |
| Open Source Alternatives | `/a0/usr/workdir/opensource_alternatives_research.md` | Chatwoot, Tiledesk, etc. — architecture reference |

