# Pulse — Testing Strategy

> Production-grade testing for a multi-tenant SaaS serving millions of users.
> Every layer is explicit. Every decision is justified. Nothing is assumed.

---

## Table of Contents

1. [Philosophy](#philosophy)
2. [What We're Protecting](#what-were-protecting)
3. [Testing Layers](#testing-layers)
4. [Framework Architecture](#framework-architecture)
5. [Backend Test Setup](#backend-test-setup)
6. [Frontend Test Setup](#frontend-test-setup)
7. [CI/CD Gates](#cicd-gates)
8. [Implementation Phases](#implementation-phases)

---

## Philosophy

Tests exist to protect **six specific failure modes**. Everything else is secondary.

| Failure | Consequence |
|---|---|
| Tenant data leakage (Workspace A reads Workspace B) | GDPR catastrophe, company-ending |
| Billing error (over/under charge) | Revenue loss, trust destruction |
| RAG wrong answers | Core product fails silently, users churn |
| SSE stream corruption | Chat appears to work but garbles messages |
| Auth bypass | Platform accessed without credentials |
| Celery task loss | KB goes stale, documents silently fail |

**Principles:**
- **Test the business logic, not the framework.** FastAPI routes are thin wrappers. Test services.
- **Tenant isolation is a first-class test concern.** Every read/write endpoint needs an isolation test.
- **Real database, real Redis in integration tests.** No mocks for storage — use test containers.
- **Mock external services** (LLMs, Stripe, Slack). Never hit real APIs in tests.
- **TDD for new features.** Write the test first, watch it fail, implement minimally.

---

## What We're Protecting

### Multi-Tenancy Boundary
Every authenticated endpoint is workspace-scoped. The pattern is:
```
/api/v1/workspaces/{workspace_id}/resource/{resource_id}
```
- `get_workspace` dependency validates `WorkspaceMembership` on every request
- `workspace_id` is validated before any resource access
- Resources are further scoped by `WHERE resource.workspace_id = workspace_id`

A test that creates data in workspace A, then tries to access it from workspace B, **must get 403 or 404, never 200**.

### Auth Stack
- JWT access tokens (30min) + refresh tokens (7d in Redis)
- argon2 password hashing
- TOTP 2FA (pyotp, Fernet-encrypted secret at rest)
- Google OAuth
- OIDC SSO (Okta, Entra, Auth0, Google Workspace)
- API keys (SHA-256 hashed, prefix-only stored)

### Data Correctness
- RAG retrieval returns the most relevant chunk, not any chunk
- Credit deductions are accurate to the token
- Ingestion pipeline produces queryable chunks
- Celery tasks are idempotent (safe to retry)

---

## Testing Layers

```
                        ┌─────────────────────────────┐
                        │   Chaos / Resilience Tests   │  ← Weekly, staging
                        ├─────────────────────────────┤
                        │     Load Tests (k6)          │  ← Nightly, staging
                        ├─────────────────────────────┤
                        │  E2E Tests (Playwright)      │  ← Nightly, staging
                        ├─────────────────────────────┤
                        │   Security Test Suite        │  ← Nightly, staging
                        ├─────────────────────────────┤
                        │  Integration Tests           │  ← Every merge to main
                        │  · Tenant Isolation Suite    │
                        │  · API Contract Tests        │
                        │  · Auth Flow Tests           │
                        ├─────────────────────────────┤
                        │  Unit Tests                  │  ← Every PR
                        │  · Backend (pytest)          │
                        │  · Frontend (Vitest)         │
                        ├─────────────────────────────┤
                        │  SAST / Lint / Type Check    │  ← Every PR
                        └─────────────────────────────┘
```

### Layer Summary

| Layer | Tool | Frequency | DB | External APIs |
|---|---|---|---|---|
| Unit — Backend | pytest + pytest-asyncio | Every PR | No (mocked) | No |
| Unit — Frontend | Vitest + React Testing Library | Every PR | No | No (MSW) |
| Integration | pytest + httpx + real DB | Every merge | Real (test DB) | Mocked |
| Tenant Isolation | pytest (subset of integration) | Every merge | Real (test DB) | No |
| E2E | Playwright | Nightly | Real (staging) | Real (staging keys) |
| Security | pytest + OWASP ZAP + custom suite | Nightly | Real (staging) | Mocked |
| Load | k6 | Nightly | Real (staging) | Mocked |
| Chaos | pumba + k6 | Weekly | Real (staging) | Mocked |

---

## Framework Architecture

### Backend Test Structure

```
backend/
├── tests/
│   ├── conftest.py               ← Global fixtures: DB, app, auth
│   ├── factories/
│   │   ├── __init__.py
│   │   ├── workspace.py          ← WorkspaceFactory, AgentFactory, MembershipFactory
│   │   ├── chatbot.py            ← ChatbotFactory, KnowledgeBaseFactory
│   │   ├── conversation.py       ← ConversationFactory, MessageFactory
│   │   └── billing.py            ← CreditLedgerFactory
│   ├── unit/
│   │   ├── test_auth.py          ← JWT, password hash, TOTP, Fernet
│   │   ├── test_rag.py           ← Retriever, reranker, confidence, generator
│   │   ├── test_billing.py       ← Credit deduction, auto-recharge, plan limits
│   │   ├── test_ingestion.py     ← Extractors, chunkers, embedder
│   │   ├── test_resolution.py    ← Escalation logic, action routing
│   │   └── test_transforms.py    ← Schema mappings, response shapes
│   ├── integration/
│   │   ├── test_tenant_isolation.py   ← All 120 endpoints, cross-workspace access
│   │   ├── test_auth_flows.py         ← Login, refresh, 2FA, SSO, OAuth
│   │   ├── test_chat.py               ← SSE streaming, escalation, lead scoring
│   │   ├── test_ingestion_api.py      ← Document create → Celery → queryable
│   │   ├── test_billing_api.py        ← Stripe webhook → credit → balance
│   │   ├── test_exceptions_api.py     ← Exception queue, reply, resolve
│   │   └── test_gdpr.py               ← Export, erasure, workspace delete
│   └── security/
│       ├── test_auth_bypass.py        ← JWT none-alg, replay, brute force
│       ├── test_idor.py               ← Resource enumeration across workspaces
│       ├── test_injection.py          ← SQL, prompt, SSRF, path traversal
│       └── test_rate_limits.py        ← Rate limit enforcement per endpoint
```

### Frontend Test Structure

```
frontend/
├── src/
│   ├── lib/
│   │   ├── __tests__/
│   │   │   ├── api-functions.test.ts  ← Transform functions (mock HTTP)
│   │   │   └── auth.test.ts           ← Token storage, expiry logic
│   │   └── test-utils/
│   │       ├── setup.ts               ← Vitest setup file
│   │       ├── msw-handlers.ts        ← Mock Service Worker API handlers
│   │       └── render.tsx             ← Custom render with providers
│   ├── stores/
│   │   └── __tests__/
│   │       ├── auth-store.test.ts
│   │       └── workspace-store.test.ts
│   └── components/
│       └── __tests__/
│           └── ChatbotTabNav.test.tsx
├── e2e/
│   ├── playwright.config.ts
│   ├── fixtures/
│   │   └── auth.ts                    ← Login helper, workspace setup
│   └── tests/
│       ├── onboarding.spec.ts
│       ├── chat.spec.ts
│       ├── exceptions.spec.ts
│       └── billing.spec.ts
└── vitest.config.ts
```

### Key Backend Fixtures (conftest.py)

```python
# Test database: separate from dev DB, created fresh per test session
# Override get_db dependency to use the test session
# Override get_current_user to return a seeded Agent
# Override get_workspace to return workspace_id directly

@pytest.fixture(scope="session")
async def engine():
    """Create test DB engine connected to test Postgres."""

@pytest.fixture
async def db(engine):
    """Async session that rolls back after each test (no committed data)."""

@pytest.fixture
async def app(db):
    """FastAPI app with get_db overridden to use test session."""

@pytest.fixture
async def client(app):
    """httpx AsyncClient for async endpoint tests."""

@pytest.fixture
async def workspace(db):
    """Pre-created workspace for tests."""

@pytest.fixture
async def agent(db, workspace):
    """Pre-created agent with owner membership."""

@pytest.fixture
async def auth_client(client, agent):
    """Client with Authorization header pre-set to agent's JWT."""
```

---

## Backend Test Setup

### Dependencies to add to `backend/pyproject.toml`

```toml
[project.optional-dependencies.dev]
# existing
pytest = ">=8.3.0"
pytest-asyncio = ">=0.24.0"
ruff = ">=0.8.0"
# add
pytest-cov = ">=6.0.0"
pytest-mock = ">=3.14.0"
pytest-xdist = ">=3.6.0"       # parallel test execution
httpx = ">=0.28.0"             # async test client (already in main deps)
faker = ">=33.0.0"             # realistic fake data
anyio = {extras=["trio"]}      # async test backend
```

### Test Database

Tests run against a **separate Postgres database** (`pulse_test`) on the same server.

```bash
# Create the test DB (run once)
docker compose exec postgres createdb -U pulse pulse_test
# Run migrations against test DB
DATABASE_URL="postgresql+asyncpg://pulse:pulse_dev_password@localhost:5433/pulse_test" \
  alembic upgrade head
```

Environment in `backend/tests/.env.test`:
```
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=pulse_test
POSTGRES_USER=pulse
POSTGRES_PASSWORD=pulse_dev_password
REDIS_HOST=localhost
REDIS_PORT=6379
JWT_SECRET_KEY=test-secret-key-not-for-production
SECRET_KEY=test-secret-key-not-for-production
FERNET_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
OPENAI_API_KEY=sk-test-not-real
```

### How Tests Run

```bash
# Unit tests only (no DB)
pytest backend/tests/unit/ -v

# Integration tests (needs running postgres + redis)
pytest backend/tests/integration/ -v

# Tenant isolation suite only
pytest backend/tests/integration/test_tenant_isolation.py -v

# Security tests
pytest backend/tests/security/ -v

# Full suite with coverage
pytest backend/tests/ --cov=app --cov-report=html --cov-fail-under=80

# Parallel (faster)
pytest backend/tests/ -n auto
```

### Makefile targets to add

```makefile
test-unit:
    pytest backend/tests/unit/ -v

test-integration:
    pytest backend/tests/integration/ -v

test-isolation:
    pytest backend/tests/integration/test_tenant_isolation.py -v

test-security:
    pytest backend/tests/security/ -v

test-all:
    pytest backend/tests/ --cov=app --cov-report=html

test-fast:
    pytest backend/tests/ -n auto --ignore=backend/tests/security/
```

---

## Frontend Test Setup

### Dependencies to add to `frontend/package.json`

```json
{
  "devDependencies": {
    "vitest": "^2.0.0",
    "@vitest/ui": "^2.0.0",
    "@vitejs/plugin-react": "^4.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.0.0",
    "@testing-library/jest-dom": "^6.0.0",
    "msw": "^2.0.0",
    "jsdom": "^25.0.0",
    "@playwright/test": "^1.49.0"
  },
  "scripts": {
    "test": "vitest",
    "test:ui": "vitest --ui",
    "test:coverage": "vitest run --coverage",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui"
  }
}
```

### Vitest config (`frontend/vitest.config.ts`)

```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/lib/test-utils/setup.ts'],
    globals: true,
    coverage: {
      reporter: ['text', 'html'],
      exclude: ['node_modules/', 'e2e/', '**/*.config.*'],
    },
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
});
```

### Playwright config (`frontend/e2e/playwright.config.ts`)

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e/tests',
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3001',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'Mobile Chrome', use: { ...devices['Pixel 5'] } },
  ],
  webServer: {
    command: 'make up',
    url: 'http://localhost:3001',
    reuseExistingServer: true,
  },
});
```

---

## CI/CD Gates

### PR checks (must pass before merge)

```yaml
# .github/workflows/pr.yml
jobs:
  backend-unit:
    run: pytest backend/tests/unit/ -v
    timeout: 2min

  frontend-unit:
    run: cd frontend && npx vitest run
    timeout: 2min

  type-check:
    run: cd frontend && npx tsc --noEmit
    timeout: 1min

  sast:
    run: |
      bandit -r backend/app/ -ll
      cd frontend && npm audit --audit-level=high
    timeout: 3min
```

### Merge to main (must pass)

```yaml
# .github/workflows/main.yml
jobs:
  integration:
    run: pytest backend/tests/integration/ -v
    needs: [postgres, redis services]
    timeout: 10min

  tenant-isolation:
    run: pytest backend/tests/integration/test_tenant_isolation.py -v
    timeout: 5min

  e2e-critical:
    run: cd frontend && npx playwright test --project=chromium e2e/tests/critical/
    timeout: 15min
```

### Nightly (staging)

```yaml
# .github/workflows/nightly.yml
jobs:
  e2e-full: 30min
  security-suite: 20min
  load-tests: 30min
  dependency-audit: 5min
```

---

## Implementation Phases

The plan is split into 8 phases, each building on the previous. **Each phase has its own detailed plan file.**

### Phase 1 — Backend Test Infrastructure
**Plan:** `docs/plans/2026-03-08-testing-phase-1-backend-infra.md`
- pytest config, conftest.py, async DB fixtures
- Factory functions for all core models
- Auth override helpers
- Makefile targets
- **Output:** `make test-unit` and `make test-integration` work

### Phase 2 — Backend Unit Tests
**Plan:** `docs/plans/2026-03-08-testing-phase-2-backend-unit.md`
- Auth: JWT, password, TOTP, Fernet
- RAG pipeline: retriever, confidence, reranker
- Billing: credit math, plan limits
- Ingestion: extractors, chunkers
- Resolution: escalation triggers, action dispatch
- **Output:** 80%+ coverage on business logic

### Phase 3 — Tenant Isolation Suite
**Plan:** `docs/plans/2026-03-08-testing-phase-3-tenant-isolation.md`
- Cross-workspace IDOR test for every endpoint
- Role escalation tests (member → admin)
- Workspace delete authorization
- **Output:** Zero tenant isolation gaps

### Phase 4 — Integration Tests
**Plan:** `docs/plans/2026-03-08-testing-phase-4-integration.md`
- Auth flows (login, refresh, 2FA, SSO)
- Chat SSE streaming
- Ingestion pipeline end-to-end
- Billing Stripe webhook flow
- GDPR export + erasure
- **Output:** Full happy-path coverage

### Phase 5 — Frontend Unit Tests
**Plan:** `docs/plans/2026-03-08-testing-phase-5-frontend-unit.md`
- Vitest setup, MSW, test-utils
- API transform functions
- Zustand store logic
- Hook tests
- **Output:** Frontend `npm test` works

### Phase 6 — E2E Tests (Playwright)
**Plan:** `docs/plans/2026-03-08-testing-phase-6-e2e.md`
- Playwright setup against docker-compose
- Register → onboarding → first chat
- Ingestion → index → chat answers
- Exception handling → agent reply
- Billing upgrade → credit increase
- **Output:** Critical path E2E suite

### Phase 7 — Security Test Suite
**Plan:** `docs/plans/2026-03-08-testing-phase-7-security.md`
- Auth bypass: JWT none-alg, replay, brute force
- IDOR: UUID enumeration
- Injection: SQL, prompt, SSRF, path traversal
- Rate limit verification
- SAST in CI (Bandit, npm audit)
- **Output:** Automated security regression suite

### Phase 8 — Load & Performance Tests
**Plan:** `docs/plans/2026-03-08-testing-phase-8-load.md`
- k6 steady-state: 500 VUs widget chat
- k6 spike: 10x for 60s
- Per-endpoint P95 latency benchmarks
- DB query EXPLAIN ANALYZE assertions
- Memory leak detection
- **Output:** Performance baselines + regression gates

---

## Coverage Targets

| Area | Target | Tool |
|---|---|---|
| Backend business logic | 80% line coverage | pytest-cov |
| Auth & security utils | 95% | pytest-cov |
| API transform functions | 100% | pytest-cov |
| Frontend transforms (api-functions.ts) | 90% | Vitest |
| Frontend stores | 80% | Vitest |
| Tenant isolation (endpoints tested) | 100% | pytest |
| E2E critical paths | 8 journeys | Playwright |

---

## Current State vs Target

| What | Now | Target |
|---|---|---|
| Backend test files | 2 (extractor unit tests) | 40+ |
| Backend test coverage | ~2% | 80% |
| Frontend test files | 0 | 20+ |
| Tenant isolation tests | 0 | 120 (one per endpoint) |
| E2E journeys covered | 0 | 8 critical paths |
| Security tests | 0 | Full suite |
| Load tests | 0 | k6 suite |
| CI test gates | `make test` only | 4-stage pipeline |
