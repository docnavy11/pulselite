# Pulse Lite

AI-powered website chatbot platform. Paste a URL, the system crawls it, auto-configures a chatbot, and gives you a `<script>` tag to embed. Primary KPI: **Autonomous Resolution Rate** — the AI resolves conversations; humans only see what it can't handle.

## Status — read this first

**Mid-rewrite, and not production software.** `main` is the v2 HTMX rewrite
described in [ARCHITECTURE.md](ARCHITECTURE.md): the React SPA, the JSON API
layer and the Celery worker fleet were removed in favour of server-rendered
Jinja2 with HTMX, asyncio background tasks and Postgres-as-queue — roughly 43K
lines across 6 containers down to ~12K across 2.

The test suite has not caught up with that. Measured on 2026-09-17:

    230 passed · 245 failed · 8 skipped · 16 errors

The failures are what the rewrite implies rather than surprises: ~130 are tests
expecting a JSON body where the server now answers with a redirect to a rendered
page, 17 parse HTML as JSON, and ~50 import `app.services.rag.*` modules the
rewrite deleted. A further 8 files are marked skipped, each naming the module it
needs rewriting against. Treat the suite as a to-do list, not as a signal that
the application is broken.

MIT licensed. Run it locally; nothing here has been hardened for the public
internet.

```bash
cd backend
POSTGRES_HOST=localhost POSTGRES_PORT=3055 pytest tests/     # from the host
make test                                                    # or inside compose
```

## Quick Start

```bash
# 1. Interactive setup — generates .env with secure keys and AI config
make setup

# 2. Start all services
make up

# 3. Run database migrations
make migrate

# 4. (Optional) Seed sample data for development
make seed
```

Or manually:

```bash
cp .env.example .env   # then edit .env
make up && make migrate
```

Open **http://localhost:3001** and log in with the admin credentials you set during setup.

> **First time?** If you haven't configured an AI provider, the app will walk you through it on first login. You can also configure it later in **Settings > AI Models**.

## Architecture

```
pulselite/
├── backend/          FastAPI + SQLAlchemy (async) + Celery
├── frontend/         React 19 + Vite + react-router-dom + Zustand
├── widget/           Embeddable chat widget — vanilla TS, Shadow DOM (5.5kb gzipped)
├── scripts/          Setup and utility scripts
├── infra/            Docker configs, Postgres init, supervisord (light mode)
├── k6/               Load testing scenarios
└── docs/             Product specs, API reference, data model, UX flows
```

### How It Works

1. **Crawl** — User pastes a URL → Celery discovers and fetches all pages
2. **Ingest** — Pages are chunked (markdown-aware), embedded, and indexed in pgvector
3. **Autoconfig** — LLM analyzes the content and generates chatbot persona, prompts, and branding
4. **Chat** — Hybrid retrieval (pgvector cosine + BM25 full-text) → Reciprocal Rank Fusion → optional reranking → LLM generation → streamed as SSE
5. **Escalation** — Low-confidence answers are escalated to the exceptions queue for human review

### Services

| Service | Port | Description |
|---|---|---|
| **Frontend** | 3001 → 3000 | React SPA (Vite dev server in Docker) |
| **Backend** | 8000 | FastAPI + Socket.IO (real-time events) |
| **Celery Worker** | — | Crawl, ingestion, autoconfig, analysis tasks |
| **Celery Beat** | — | Scheduled tasks (data retention, analytics) |
| **PostgreSQL** | 5433 → 5432 | pgvector + pg_trgm extensions |
| **Redis** | 6379 | Cache, Celery broker, Socket.IO adapter |

### Multi-Tenant

All data is workspace-scoped. Every authenticated route follows the pattern:
```
/api/v1/workspaces/{workspace_id}/...
```

## Configuration

### Interactive Setup

```bash
make setup          # guided .env wizard — generates secure keys, configures AI
make setup-check    # validate an existing .env file
```

### AI Provider

Pulse Lite uses any **OpenAI-compatible API** (OpenRouter, OpenAI, Anthropic, Ollama, etc.). Configure via:

1. **Environment** — Set `AI_API_KEY` + `AI_BASE_URL` in `.env` (applies to all workspaces)
2. **UI** — Per-workspace in **Settings > AI Models** (overrides env)

```bash
# Examples:
AI_BASE_URL=https://openrouter.ai/api/v1    AI_API_KEY=sk-or-v1-...
AI_BASE_URL=https://api.openai.com/v1       AI_API_KEY=sk-...
AI_BASE_URL=http://localhost:11434/v1        AI_API_KEY=ollama
```

Fallback chain: workspace key → `AI_API_KEY` env var → setup wizard on login.

### Environment Variables

See [`.env.example`](.env.example) for the full list with documentation. Key groups:

| Group | Variables | Required? |
|---|---|---|
| **Database** | `POSTGRES_*` | Defaults work with bundled Docker |
| **Redis** | `REDIS_HOST`, `REDIS_PORT` | Defaults work with bundled Docker |
| **Security** | `SECRET_KEY`, `JWT_SECRET_KEY`, `FERNET_KEY` | Yes — `make setup` generates these |
| **Admin** | `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Yes — first user, created on startup |
| **AI** | `AI_BASE_URL`, `AI_API_KEY`, `DEFAULT_CHATBOT_MODEL` | Needed for chatbots to work |
| **URLs** | `BASE_URL`, `FRONTEND_URL`, `VITE_API_URL` | Defaults work for local Docker |
| **Integrations** | Google OAuth, Slack, Notion, Shopify, etc. | Optional — leave empty to disable |
| **Billing** | `STRIPE_*`, `CLOUD_MODE` | Optional — self-hosted has all features unlocked |

## Development

### Prerequisites

- Docker & Docker Compose
- Python 3 (for `make setup` only — runs on host)
- Node.js (for E2E tests only — runs on host)

### Common Commands

```bash
# Services
make up                     # start all containers
make down                   # stop all containers
make build                  # rebuild images
make logs                   # tail all container logs

# Database
make migrate                # run pending migrations
make migrate-create msg="description"  # create new migration
make seed                   # seed dev data
make reset-db               # full reset: destroy volumes, recreate, migrate, seed

# Shells
make shell-backend          # bash into backend container
make shell-db               # psql into postgres
```

### Testing

```bash
# Backend (pytest)
make test                   # all tests
make test-unit              # tests/unit/ only
make test-integration       # tests/integration/ only
make test-security          # tests/security/ (tenant isolation)
make test-coverage-gate     # pytest + coverage ≥ 45%

# Frontend (Vitest)
make test-frontend          # unit tests
make test-frontend-coverage # with coverage report

# E2E (Playwright — needs Docker up + seeded)
make test-e2e               # headless
make test-e2e-headed        # with browser

# Linting
make lint                   # ruff check + format check
make format                 # ruff auto-fix

# Security scanning
make lint-security-static   # bandit + semgrep

# API fuzz / load
make test-schema            # schemathesis (public + authenticated)
make perf-all               # k6 smoke + auth + widget scenarios
```

**Running a single test:**

```bash
docker compose exec backend pytest tests/unit/test_auth_service.py -v
docker compose exec backend pytest tests/ -k "test_name" -v
```

### Code Style

- Python: Ruff, 120-char lines, Python 3.12 target (see `backend/pyproject.toml`)
- Frontend: TypeScript strict, Tailwind CSS
- After any Python change: `docker compose restart backend`

### Adding a New Page

1. Create `frontend/src/app/(dashboard)/your-route/page.tsx`
2. Add route in `frontend/src/App.tsx` (react-router-dom `<Route>`)
3. Add sidebar link in `frontend/src/components/layout/Sidebar.tsx`
4. Add API function in `frontend/src/lib/api-functions.ts`
5. Add types in `frontend/src/lib/types.ts`

> **Note:** Despite the `app/(dashboard)/` directory structure (which mimics Next.js conventions), routing uses **react-router-dom** via `App.tsx`. This is a Vite-based React SPA, not Next.js.

## Deployment

### Self-Hosted (Docker Compose)

The standard `docker-compose.yml` runs 6 services. For production:

1. Run `make setup` and set strong keys
2. Set `AI_BASE_URL` and `AI_API_KEY` for your LLM provider
3. Update URLs if behind a reverse proxy (`BASE_URL`, `FRONTEND_URL`, etc.)
4. `make up && make migrate`

### Lightweight (Single Container)

For simpler deployments, the lightweight mode runs backend + frontend + Redis in a single container:

```bash
docker compose -f docker-compose.light.yml up -d
```

Only PostgreSQL runs separately. See `Dockerfile.light` and `infra/light/` for details.

### Cloud Mode

Set `CLOUD_MODE=true` to enable SaaS features: Stripe billing, credit system, plan tier limits, BYOK credit discounts. When `false` (default), all features are unlocked with no billing.

## Troubleshooting

Pulse Lite is designed to surface clear errors instead of failing silently. Here's what to check when things go wrong.

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

Returns `200` with `"status": "healthy"` when everything is working, or `503` with `"status": "degraded"` and per-check details when something is down. Checks database, Redis, and AI configuration.

### Startup Warnings

On every startup the backend runs pre-flight checks and logs actionable warnings:

| Warning | What to do |
|---|---|
| `SECRET_KEY is using the default dev value` | Run `make setup` or generate: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `FERNET_KEY is not set` | Generate: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ADMIN_EMAIL/ADMIN_PASSWORD not set` | Set in `.env` — needed to create the first user on startup |
| `AI_API_KEY is not set` | Chatbots won't work — set `AI_API_KEY` + `AI_BASE_URL` in `.env` or configure in Settings > AI Models |
| `AI_API_KEY is set but AI_BASE_URL is empty` | Add `AI_BASE_URL` (e.g. `https://openrouter.ai/api/v1`) |

### Common Errors

| What you see | Cause | Fix |
|---|---|---|
| **Setup wizard on every login** | AI not configured (no API key or no models selected) | Set `AI_API_KEY` + `AI_BASE_URL` in `.env`, or configure in Settings > AI Models |
| **"No AI provider configured" on chatbot create** | Neither env `AI_API_KEY` nor workspace key is set | Add key in `.env` or Settings > AI Models |
| **"No AI base URL configured" on model fetch** | `AI_BASE_URL` is empty | Set `AI_BASE_URL` in `.env` (e.g. `https://openrouter.ai/api/v1`) |
| **Chatbot "Setup failed"** | Autoconfig LLM call failed — hover the card to see the reason | Check the error (usually wrong API key, unreachable URL, or invalid model) |
| **Chat returns "AI provider authentication failed"** | LLM API rejected the key | Verify `AI_API_KEY` is correct and not expired |
| **Chat returns "Cannot connect to AI provider"** | `AI_BASE_URL` unreachable from the server | Verify the URL is correct and accessible from inside Docker |
| **Frontend can't reach backend** | `VITE_API_URL` mismatch or backend not running | Check `make logs`, verify `VITE_API_URL` in `.env` matches where the backend is running |
| **Health check returns 503** | Database or Redis unreachable | Check `POSTGRES_HOST`/`REDIS_HOST` and that containers are running (`docker compose ps`) |
| **All users logged out after restart** | `JWT_SECRET_KEY` was changed | Use a stable key — don't regenerate between restarts |

### Validate Your `.env`

```bash
make setup-check
```

Scans your `.env` for missing required values, default dev keys, and AI config issues.

## Key Concepts

| Concept | Description |
|---|---|
| **Workspace** | Tenant unit — all data, chatbots, and settings are workspace-scoped |
| **Chatbot** | An AI agent with its own knowledge base, persona, widget config, and LLM settings |
| **Knowledge Base** | Crawled + ingested content that powers a chatbot's answers |
| **Exceptions Queue** | Conversations the AI escalated — the ~10% that need human attention |
| **Gap Clusters** | Groups of unanswered questions — surfaces what's missing from the KB |
| **Resolution Rate** | % of conversations resolved autonomously without human intervention |

## API

Interactive docs: **http://localhost:8000/api/docs** (Swagger UI)

**Public endpoints** (no auth):
- `GET /api/v1/health` — health check
- `GET /api/v1/widget/{chatbot_id}/config` — widget configuration
- `POST /api/v1/public/chat` — chat endpoint (rate-limited, SSE)
- `GET /api/v1/config/deployment` — deployment mode

**Authenticated endpoints** follow the pattern:
```
GET/POST/PUT/DELETE /api/v1/workspaces/{workspace_id}/chatbots
GET/POST/PUT/DELETE /api/v1/workspaces/{workspace_id}/conversations
GET/POST/PUT/DELETE /api/v1/workspaces/{workspace_id}/knowledge-bases
...
```

Auth: JWT in `Authorization: Bearer <token>` header. Tokens obtained via `POST /api/v1/auth/login`.

## Documentation

| File | Contents |
|---|---|
| [`docs/PRODUCT_BLUEPRINT.md`](docs/PRODUCT_BLUEPRINT.md) | Vision, positioning, full feature spec |
| [`docs/api_reference.md`](docs/api_reference.md) | All API routers — endpoints, params, responses |
| [`docs/deployment.md`](docs/deployment.md) | Production deployment guide |
| [`docs/pulse_data_model.md`](docs/pulse_data_model.md) | 32-table SQL schema |
| [`docs/pulse_ux_flows.md`](docs/pulse_ux_flows.md) | Screen-by-screen UX flows |
| [`docs/gaps.md`](docs/gaps.md) | Feature gap list (prioritized) |
| [`docs/rag_chunking_research.md`](docs/rag_chunking_research.md) | RAG pipeline design decisions |

## License

Proprietary. All rights reserved.

## Licence

MIT — see [LICENSE](LICENSE).
