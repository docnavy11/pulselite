# Changelog

All notable changes to Pulse are documented here.

## [0.1.0] — 2026-03-07 — Phase 1 MVP

Initial release of the Pulse AI-native autonomous resolution platform.

### Backend

**Auth & Workspace**
- JWT authentication (access 30min + refresh 7d stored in Redis)
- Google OAuth 2.0 login
- Multi-workspace support — all data workspace-scoped
- Onboarding progress tracking (step-based)

**RAG Pipeline**
- Hybrid retrieval: pgvector cosine similarity + BM25 full-text search (pg_trgm)
- Cross-encoder reranking for precision
- Multi-model LLM support: OpenAI GPT-4o, Anthropic Claude, Google Gemini
- BYOK (Bring Your Own Key) with Fernet encryption for customer API keys
- Streaming chat responses via Server-Sent Events (SSE)

**Knowledge Base**
- Document ingestion from URL and file upload (PDF, TXT, DOCX)
- Async Celery pipeline for chunking, embedding, and indexing
- Living Knowledge Base — article CRUD with publish-to-vector-store
- Document reindex on demand

**Exceptions Queue**
- Automatic escalation detection with configurable confidence threshold
- Escalation reason tracking (low_confidence, no_answer, user_request, etc.)
- Human reply endpoint (with optional simultaneous resolve)
- AI-generated suggested action per exception (async, via Celery)

**Intelligence Layer**
- Gap cluster detection: unanswered questions grouped by BERTopic clustering
- AI-drafted articles auto-generated for each gap cluster
- Topic clustering across all conversations
- Sentiment trend analysis over time
- Feature request extraction
- Lead scoring with hot/warm/cold tier classification
- Per-conversation analysis (topics, sentiment, signals)

**Integrations**
- Slack, Intercom, Zendesk, Crisp integration configuration
- Connection test endpoint

**Billing**
- Stripe Checkout and Customer Portal integration
- 4 billing plans: Free, Starter ($49), Growth ($149), Enterprise ($499)
- AI credit tracking (balance, history)

**GDPR**
- Data export trigger + download
- Contact deletion (right to erasure)
- Workspace deletion

**API**
- 22 FastAPI routers, 19 authenticated + 3 public
- OpenAI-compatible completions endpoint
- Public chat endpoint (rate-limited: 20 req/min per IP)
- Widget config public endpoint
- Shareable chat link endpoint

**Infrastructure**
- Docker Compose stack: postgres, redis, backend, celery_worker, celery_beat, frontend
- 32-table PostgreSQL schema with pgvector + pg_trgm extensions
- 14 Celery tasks across ingestion, analysis, clustering, alert, and billing queues
- 4 Alembic migrations
- Alembic migration tooling

### Frontend

**Pages (31 total)**
- Auth: login, register
- Dashboard: resolution rate, stats, charts (Recharts)
- Chatbots: list, detail (sources + settings tabs), test chat (streaming), widget customization, deploy
- Conversations: list view
- Exceptions Queue: list + detail with customer context panel and suggested action
- Intelligence: gaps, topics, sentiment trends, feature requests, leads
- Settings: billing, integrations, general

**Key features**
- JWT token management with auto-refresh (Axios interceptor)
- Workspace auto-load on every authenticated page
- Streaming chat via SSE (token-by-token display)
- Widget customizer with live preview
- Deploy page: embed script, QR code generator, REST API guide, API key management
- Syntax-highlighted code blocks (Prism)

**Tech stack**
- Next.js 15.3.9 (App Router) + React 19 + TypeScript
- Tailwind CSS 3 + clsx
- Zustand for auth + workspace state
- Recharts for dashboard visualizations
- react-dropzone for file uploads
- qrcode.react for QR code generation

### Widget

- Vanilla TypeScript, Shadow DOM (style isolation)
- Rollup bundle — 5.5kb gzipped
- Script tag embed: `<script src="..." data-chatbot-id="...">`
