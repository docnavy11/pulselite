# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is
AI-native autonomous resolution platform. FastAPI backend + Next.js 15 frontend + Celery workers. Multi-tenant SaaS — every API route is workspace-scoped.

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

## Testing

```bash
# Backend
make test                    # all pytest (234 tests)
make test-unit               # tests/unit/ only
make test-integration        # tests/integration/ only
make test-security           # tests/security/ (tenant isolation)
make test-coverage-gate      # pytest + cov-fail-under=45 (workers excluded)

# Frontend
make test-frontend           # Vitest (53 tests)
make test-frontend-coverage

# E2E
make test-e2e                # Playwright (22 tests, needs Docker up + seeded)
make test-e2e-headed

# Static security
make lint-security-static    # bandit + semgrep

# API fuzz
make test-schema-public      # schemathesis against public endpoints
make test-schema             # schemathesis public + authenticated

# Load
make perf-smoke              # k6 health (5 VUs/20s)
make perf-auth               # k6 authenticated reads (10 VUs/30s)
make perf-widget             # k6 widget config (20 VUs/30s)
make perf-all                # all three k6 scenarios

# Run a single test
docker compose exec backend pytest tests/unit/test_auth_service.py -v
docker compose exec backend pytest tests/ -k "test_name" -v
```

Coverage config (workers excluded) is in `backend/pyproject.toml` under `[tool.coverage.run]`.

## Backend architecture

### Route structure
All authenticated routes: `/api/v1/workspaces/{workspace_id}/...`
`workspace_id` is validated + membership-checked via `Depends(get_workspace)`.

Public exceptions:
- `GET /api/v1/health`
- `GET /api/v1/widget/{chatbot_id}/config`
- `POST /api/v1/public/chat` (rate-limited, SSE)
- `GET /api/v1/billing/plans`

### Key files
- `backend/app/main.py` — all 34 routers registered
- `backend/app/api/v1/` — route handlers (one file per domain)
- `backend/app/services/` — business logic (called by routes)
- `backend/app/models/` — SQLAlchemy mapped classes
- `backend/app/schemas/` — Pydantic request/response models
- `backend/app/config.py` — all env var settings (pydantic-settings)
- `backend/app/workers/tasks/` — 14 Celery tasks (excluded from coverage gate)

### Auth flow
JWT access token (30 min) + refresh (7d, stored in Redis). Tokens in `Authorization: Bearer` header. `Depends(get_current_user)` on every protected route. Google OAuth and OIDC SSO also supported (`backend/app/api/v1/sso.py`).

### RAG pipeline
Hybrid retrieval: pgvector cosine similarity + BM25 FTS → cross-encoder reranking → multi-model LLM (OpenAI/Anthropic/Google). Entry point: `backend/app/services/resolution_service.py`.

### Ingestion
Celery task `ingest_document` → extractors in `backend/app/services/ingestion/extractors/` (PDF, DOCX, sitemap, web, Notion, Google Drive, Dropbox, Zendesk, Salesforce). Uses `defusedxml` for XML parsing (XXE-safe).

## Frontend architecture

### API layer
All API calls live in `frontend/src/lib/api-functions.ts`. Every function takes `workspaceId` as first argument. `ApiClient` in `frontend/src/lib/api.ts` handles auth headers, 401 retry with token refresh.

### State
- `useWorkspaceStore` (Zustand) — current workspace + workspace list. `ProtectedRoute` populates it on mount; pages access `useWorkspaceStore(s => s.currentWorkspace)` directly.
- `useAuthStore` (Zustand) — user + tokens, persisted to localStorage via `frontend/src/lib/auth.ts`.

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
2. Sidebar link: `frontend/src/components/layout/Sidebar.tsx`
3. API function: `frontend/src/lib/api-functions.ts`
4. Types: `frontend/src/lib/types.ts`

### Testing (frontend)
- Unit tests: `frontend/src/test/` — Vitest + MSW v2 (`msw/node` setupServer)
- E2E: `frontend/e2e/` — Playwright, auth reused via `storageState` (`e2e/.auth/user.json`)
- MSW handlers match `http://localhost:8000/api/v1/...`
- Zustand store reset between tests: `useAuthStore.setState({ user: null, tokens: null, isLoading: true })`

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
