# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is
Dead-simple website chatbot — paste a URL, the system crawls it, auto-configures the chatbot, and returns a `<script>` tag. FastAPI backend + React (Vite + react-router-dom) frontend + Celery workers. Multi-tenant SaaS — every API route is workspace-scoped.

## Port range
This project uses ports **3050–3060**. All services must bind within this range.

## Running the project
```bash
make up          # start all Docker containers
make migrate     # run DB migrations
make seed        # seed dev data
```

- Frontend: http://localhost:3001 (Docker maps 3001→3000)
- Backend: http://localhost:8000 / API docs: http://localhost:8000/api/docs
- Dev credentials: `test@pulse.dev` / `test`
- Dev workspace ID: `350863e7-3dc8-430e-bc23-fd41d4499d7b`
- Dev chatbot ID: `a8dfa0e8-b077-4bcc-9d2a-00bdf3e4f108`

After any Python change: `docker compose restart backend`

### Database migrations
```bash
make migrate                           # run pending migrations (alembic upgrade head)
make migrate-create msg="description"  # create new migration (alembic revision --autogenerate)
make reset-db                          # full reset: destroy volumes, recreate, migrate, seed
```

### Useful shell access
```bash
make shell-backend    # bash into backend container
make shell-db         # psql into postgres
make logs             # follow Docker logs
```

## Testing

```bash
# Backend
make test                    # all pytest
make test-unit               # tests/unit/ only
make test-integration        # tests/integration/ only
make test-security           # tests/security/ (tenant isolation)
make test-coverage-gate      # pytest + cov-fail-under=45 (workers excluded)

# Frontend
make test-frontend           # Vitest
make test-frontend-coverage

# E2E
make test-e2e                # Playwright (needs Docker up + seeded)
make test-e2e-headed

# Static security
make lint-security-static    # bandit + semgrep

# API fuzz / load
make test-schema             # schemathesis public + authenticated
make perf-all                # k6 smoke + auth + widget scenarios

# Run a single test
docker compose exec backend pytest tests/unit/test_auth_service.py -v
docker compose exec backend pytest tests/ -k "test_name" -v
```

```bash
# Linting
make lint                    # ruff check + format check
make format                  # ruff format (auto-fix)
```

Ruff config: Python 3.12 target, 120-char line length (`backend/pyproject.toml`). Coverage config (workers excluded) is in `backend/pyproject.toml` under `[tool.coverage.run]`.

## Backend architecture

### Route structure
All authenticated routes: `/api/v1/workspaces/{workspace_id}/...`
`workspace_id` is validated + membership-checked via `Depends(get_workspace)`.

Public exceptions:
- `GET /api/v1/health`
- `GET /api/v1/widget/{chatbot_id}/config`
- `POST /api/v1/public/chat` (rate-limited, SSE)
- `GET /api/v1/billing/plans` (returns 404 in self-hosted mode)
- `GET /api/v1/config/deployment`

### Key files
- `backend/app/main.py` — all routers registered
- `backend/app/api/v1/` — route handlers (one file per domain)
- `backend/app/services/` — business logic (called by routes)
- `backend/app/models/` — SQLAlchemy mapped classes
- `backend/app/schemas/` — Pydantic request/response models
- `backend/app/config.py` — all env var settings (pydantic-settings)
- `backend/app/workers/tasks/` — Celery tasks (excluded from coverage gate)

### Auth flow
JWT access token (30 min) + refresh (7d, stored in Redis). Tokens in `Authorization: Bearer` header. `Depends(get_current_user)` on every protected route. Google OAuth and OIDC SSO also supported (`backend/app/api/v1/sso.py`).

### Celery task pattern
Every task wraps async code in `asyncio.run()`, which creates a fresh event loop. **Always call `await engine.dispose()` first** — a new event loop invalidates the existing connection pool, causing "Future attached to a different loop" errors otherwise.

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def my_task(self, arg: str) -> dict:
    try:
        return asyncio.run(_run(arg))
    except Exception as exc:
        raise self.retry(exc=exc)

async def _run(arg: str) -> dict:
    await engine.dispose()          # REQUIRED — clear stale pool
    async with async_session_factory() as session:
        ...
```

### Crawl pipeline
`POST /crawl` → `prepare_crawl()` creates KB + `CrawlJob` (status=`pending`), commits, returns `job_id` immediately → fires `crawl_website.delay(job_id)` → Celery task calls `execute_crawl()` which discovers URLs, fetches each page, commits `pages_queued += 1` after every page (live progress), then fires `ingest_document.delay(doc_id)` for each document.

**Critical ordering**: `ingest_document.delay()` must be called **after** `db.commit()`. Workers read from the DB — dispatching before commit causes a race where the worker finds no row.

### RAG pipeline
Entry point: `backend/app/services/resolution_service.py`

1. Hybrid retrieval: pgvector cosine (top 20) + BM25 FTS (top 20) → Reciprocal Rank Fusion
2. Optional cross-encoder reranking (`chatbot.use_reranking`)
3. Confidence check: if `max_score < chatbot.confidence_threshold` → escalate
4. LLM generation via `get_llm_client(provider)` — supports OpenAI, Anthropic, Google, OpenRouter
5. Streamed as SSE: `token` events → `done` event (with metadata) or `error` event

**LLM clients**: always use `get_llm_client()` from `app.services.llm`. The app is configured with `OPENROUTER_API_KEY` — use `OpenRouterLLMClient` for internal services (e.g. autoconfig). Never instantiate `AnthropicLLMClient` or `OpenAILLMClient` directly unless the user supplies their own key.

### Real-time (Socket.IO)
Backend: `python-socketio` server mounted as combined ASGI app in `main.py`. Redis adapter (`AsyncRedisManager`) enables events from both the API process and Celery workers.

- `backend/app/services/realtime.py` — `emit_to_workspace(workspace_id, event, data)` helper. Write-only Redis manager, lazy-initialized, gracefully handles Redis unavailability.
- Frontend: `frontend/src/lib/socket.ts` — singleton client with JWT auth, auto-joins workspace room. `useSocketEvent<T>(event, handler)` React hook for subscribing to events.
- Events: `crawl:progress`, `crawl:completed`, `document:status_changed`, `chatbot:status_changed`, `workspace:usage_updated`
- Workspace rooms keyed by `workspace:{id}` for multi-tenant isolation.

**Pattern for emitting from workers**: import `emit_to_workspace` from `app.services.realtime` — it creates its own write-only Redis manager, no access to the Socket.IO server process needed.

### Ingestion
Celery task `ingest_document` → extractors in `backend/app/services/ingestion/extractors/` → chunkers in `backend/app/services/ingestion/chunkers/`. Document status: `pending → processing → indexed` (or `failed`). Crawled pages use `source_type="text"` with `raw_content` pre-populated to skip re-fetching.

**Chunkers**: `markdown_chunker.py` splits by headings and merges small sections (< 64 tokens) up to TARGET_TOKENS (512). `qa_chunker.py` groups Q&A pairs up to TARGET_TOKENS. Both produce `{content, heading_path, token_count}` dicts.

**Autoconfig completion**: when the last document finishes ingesting, `ingest_document` atomically transitions the KB status from `crawling` → `configuring` and fires `run_autoconfig_for_chatbot.delay()`. Only one worker wins the atomic UPDATE — prevents duplicate autoconfig runs.

### UUIDPrimaryKeyMixin gotcha
`server_default=text("gen_random_uuid()")` is DB-side only. SQLAlchemy will not populate `obj.id` in Python before the INSERT unless you explicitly pass `id=uuid.uuid4()`. Always pass an explicit `id=uuid.uuid4()` when creating model instances in service code; rely on the DB default only for cases where you immediately flush/commit and then refresh.

## Frontend architecture

**Important**: despite the `app/(dashboard)/` directory structure (which mimics Next.js conventions), routing is **react-router-dom** via `frontend/src/App.tsx`. This is a Vite-based React SPA, not a Next.js app.

### API layer
All API calls live in `frontend/src/lib/api-functions.ts`. Every function takes `workspaceId` as first argument. `ApiClient` in `frontend/src/lib/api.ts` handles auth headers, 401 retry with token refresh.

### State (Zustand stores in `frontend/src/stores/`)
- `useWorkspaceStore` — current workspace + workspace list. `ProtectedRoute` populates it on mount by calling `GET /api/v1/workspaces` and setting `currentWorkspace` to the first result. Pages access `useWorkspaceStore(s => s.currentWorkspace)` directly.
- `useAuthStore` — user + tokens, persisted to localStorage via `frontend/src/lib/auth.ts`.
- `useChatbotStore` — current chatbot (detail view) + chatbots list. Keeps `currentChatbot` and `chatbots[]` in sync when patching.

### Response shape transforms
Several backend responses differ from frontend types — transforms happen inside `api-functions.ts`:

| Endpoint | Backend | Frontend |
|---|---|---|
| `GET /exceptions` | `{items, total}` | `Exception[]` |
| `GET /exceptions/{id}` | `{conversation, messages, contact_context}` | `Exception` (escalation_reason from conversation) |
| `GET /sentiment-trends` | `{data: [{date, avg_sentiment, count}]}` | `SentimentData[]` |
| `GET /credits/balance` | `{balance, used, limit, plan}` | `CreditBalance` |

### Adding a new page
1. `frontend/src/app/(dashboard)/your-route/page.tsx`
2. Route in `frontend/src/App.tsx` (react-router-dom `<Route>`)
3. Sidebar link: `frontend/src/components/layout/Sidebar.tsx`
4. API function: `frontend/src/lib/api-functions.ts`
5. Types: `frontend/src/lib/types.ts`

### Testing (frontend)
- Unit tests: `frontend/src/test/` — Vitest + MSW v2 (`msw/node` setupServer)
- E2E: `frontend/e2e/` — Playwright, auth reused via `storageState` (`e2e/.auth/user.json`)
- MSW handlers match `http://localhost:8000/api/v1/...`
- Zustand store reset between tests: `useAuthStore.setState({ user: null, tokens: null, isLoading: true })`

## Test infrastructure

### Test database
Tests use a separate `pulse_test` database (configured in `backend/tests/conftest.py` via `os.environ["POSTGRES_DB"] = "pulse_test"`). **Migrations must be applied to both databases** — `make migrate` only targets `pulse`. To migrate the test DB: `docker compose exec backend bash -c "POSTGRES_DB=pulse_test PYTHONPATH=/app alembic upgrade head"`. PostgreSQL extensions required: `uuid-ossp`, `vector` (pgvector), `pg_trgm` (trigram search) — initialized via `infra/postgres/init.sql`.

### Backend fixture architecture
`backend/tests/conftest.py` uses nested transactions (savepoints) for zero-overhead isolation — each test rolls back to its savepoint rather than truncating tables. `asyncio_mode = "auto"` in `pyproject.toml` — async tests don't need `@pytest.mark.asyncio`.

- `db` (function-scoped) — `AsyncSession` with `join_transaction_mode="create_savepoint"`; rolls back after every test
- `workspace` / `agent` / `auth_client` (function-scoped) — pre-seeded entities with a valid JWT
- `second_workspace` — used for tenant isolation tests (workspace substitution + IDOR)

### Factories
`backend/tests/factories.py` — `make_chatbot()`, `make_knowledge_base()`, `make_document()`, `make_conversation()`, `make_message()`. All use `await db.flush()` (not commit) — IDs are assigned but data is rolled back after the test.

## CI/CD

GitHub Actions at `.github/workflows/ci.yml` — 5 jobs on push/PR to `main`:

```
lint → backend-tests → e2e
lint → frontend-tests → e2e
backend-tests → schema-perf
```

CI uses `cp .env.example .env` — no secrets required for the test suite.

## Security notes
- All webhook endpoints (Meta, Slack) must return HTTP 200 even on malformed input — they catch all exceptions
- SSO discovery URLs validated as HTTPS-only (`_validate_https_url` in `sso.py`); token/userinfo endpoints from discovery docs also validated before use
- Sitemaps parsed with `defusedxml` (XXE-safe); URL scheme validated before fetch
- SOQL queries in Salesforce action sanitize email input before interpolation
- Input fields validated against null bytes across all schemas
- Widget public chat endpoint checks `Origin` against `chatbot.widget_config.allowed_domains`

## Deployment modes
`CLOUD_MODE` env var (default `false`). When `false` (self-hosted): all features unlocked, billing/credits/plan limits disabled, `require_cloud` dependency returns 404 on billing routes. When `true` (cloud): full SaaS with Stripe billing, credit system, plan tier limits. BYOK workspaces (`is_byok=true`) get 50% credit discount. Plan tiers stored in `plan_tiers` table, cached at startup via `plan_service.load_plan_tiers()`.

Key files:
- `backend/app/services/deployment.py` — `is_cloud()`, `is_self_hosted()`, `require_cloud` dependency
- `backend/app/services/plan_service.py` — `get_plan_tier()`, `get_plan_limits()`, `has_feature()`, cached at startup
- `backend/app/models/plan_tier.py` — `PlanTier` model (slug PK, limits, features JSONB)
- `frontend/src/stores/deployment-store.ts` — `useDeploymentStore` Zustand store with `isCloud` flag


## Infrastructure conventions

<!-- infra-pointer:start — managed block, safe to regenerate -->

This project is covered by the infrastructure documentation in
**[docnavy11/infra](https://github.com/docnavy11/infra)** (private). Read the
relevant page before changing how this project is built, deployed or configured.
On the dev server the checkout is at `/home/dev/projects/infra`.

| Question | Document |
|---|---|
| How does deployment work here? | `README.md` — the `deploy.sh` + `infra/` + `dist/` convention |
| How do I deploy, debug a 502, or restore? | `runbooks.md` |
| Which domain does this serve, and from where? | `services.md` |
| What is this project's state and known traps? | `projects/pulselite.md` |
| Where does everything live? | `architecture.md` |
| What is backed up, and how do I restore it? | `backups.md` |
| Known security gaps, and where secrets live | `security.md` |
| What is still outstanding? | `TODO.md` |

### Rules

- **Deploy only with `./deploy.sh`, from the dev server.** Never edit files
  directly on prod — the next deploy runs `rsync --delete` and silently
  overwrites them.
- **Never commit secrets.** Real `.env` files stay on the server at mode 600;
  commit an `env.example` documenting the required keys instead.
- **Never pin a Traefik route to a container IP or a full container name.** Both
  change on redeploy. Use a container name for `/opt` stacks, or a
  `service: http-0-<app-uuid>@docker` reference for Coolify apps. See
  `runbooks.md`.
- **Directory names are not reliable.** `intools-ai` serves
  `beteretools.linkflow.be`; `AI-readiness` serves `ai-eu-readiness.linkflow.be`;
  `scraper` is the Video Knowledge Base. Confirm via `deploy.sh`, not the name.

### If reality does not match these docs, report it

Drift is a defect, not an inconvenience — an undocumented deviation is how a
route silently 502s for weeks, or how a token ends up in a world-readable file.

1. **Do not silently work around it.**
2. State plainly what you found and what the docs claim.
3. If the docs are wrong, fix them in the infra repo.
4. If neither is right, add it to `infra/TODO.md` rather than leaving it
   undocumented.

Check this project against the documented conventions:

```bash
/home/dev/projects/infra/check-project.sh
```

It validates version control, unpushed work, tracked secrets, the deploy
convention, and whether the live domain actually responds. Exit 0 means no
failures.

<!-- infra-pointer:end -->