# Comprehensive Testing Strategy — Design Spec

## Overview

A bottom-up, phased testing strategy to bring PulseLite from 45% coverage with 32 broken tests to 90%+ enforced coverage across backend (including workers), frontend, contract tests, and E2E — suitable for an open-source product with a commercial offering.

**Approach:** Layer-by-layer through the test pyramid. Each phase produces a self-contained improvement with a progressive coverage gate ramp (45% → 70% → 80% → 90%).

**Scope:** 7 phases, 10 implementation cycles.

## Current State

- **573 total tests** (386 backend, 187 frontend)
- **32 pre-existing failures** (13 backend, 19 frontend)
- **Coverage gate:** 45% backend, none frontend
- **Workers excluded** from coverage
- **9 services** with zero unit tests
- **8+ route groups** with zero integration tests
- **No contract tests**
- **4 E2E flows** (auth, chatbots, dashboard, conversations)

## Prerequisite: Test Database Migration

All phases require the `pulse_test` database to be in sync with `pulse`. Before starting any phase, run:
```bash
docker compose exec backend bash -c "POSTGRES_DB=pulse_test PYTHONPATH=/app alembic upgrade head"
```
Phase 6 automates this in CI, but until then it must be done manually before running tests.

## Phase 0: Green Baseline

Fix all 32 pre-existing test failures. No new tests.

### Backend (13 failures)

| Test File | Count | Root Cause | Fix |
|-----------|-------|-----------|-----|
| `test_content_hash_skip.py` | 3 | Vector dimension mismatch (1536 vs 384) after embedding model change | Update mock embedding dimensions to 384 |
| `test_email_service.py` | 3 | Assertions broken after Resend/SMTP provider refactor | Update mocks and assertions to match new provider interface |
| `test_emit_task_event.py` | 4 | Mock targets stale `_create_manager` attribute in `realtime.py` | Update mock target to current realtime module internals |
| `test_realtime.py` | 2 | Same `_create_manager` issue | Same fix as emit_task_event |
| `test_ingest_completion_check.py` | 1 | `StopAsyncIteration` from async generator mock | Fix async generator mock to yield properly |

### Frontend (19 failures)

| Test File | Count | Root Cause | Fix |
|-----------|-------|-----------|-----|
| `socket.test.ts` | 4 | `useWorkspaceStore.subscribe` not a function — mock doesn't match Zustand v4 subscribe API | Update mock to provide two-arg `subscribe(listener, selector)` |
| `activity-console.test.ts` | 9 | Cascading from socket mock issue | Fixed by socket mock fix |
| `realtime-notifications.test.ts` | 6 | Same root cause | Fixed by socket mock fix |

### Deliverable

- All existing tests pass
- Coverage gate stays at 45%
- One branch, one PR

## Phase 1: Backend Unit Tests — Fill Service Gaps

Target 9 untested services plus all Celery workers. Largest phase by volume.

### Untested services

| Service | Priority | Complexity | What to test |
|---------|----------|-----------|-------------|
| `resolution_service.py` | Critical | High | RAG pipeline: retrieval → reranking → confidence check → LLM generation → SSE streaming. Mock vector DB, BM25, reranker, LLM client. Test escalation logic, credit deduction (cloud mode), conversation cap. |
| `knowledge_base_service.py` | High | Medium | KB CRUD, document listing, status transitions, indexing stats |
| `document_service.py` | High | Medium | Document CRUD, extraction dispatch, status transitions |
| `qa_service.py` | Medium | Low | Q&A pair CRUD, workspace scoping |
| `article_service.py` | Medium | Low | Article CRUD, workspace scoping |
| `action_service.py` | Medium | Low | Action CRUD, validation |
| `encryption.py` | Medium | Low | Fernet encrypt/decrypt round-trip, invalid key handling |
| `billing.py` | Medium | Medium | Stripe checkout/portal session creation (mock Stripe SDK), webhook event handling, plan transitions |
| `webhooks.py` | Medium | Low | Webhook config CRUD |
| `crawl_service.py` | Medium | Medium | Crawl preparation, URL validation, job creation |

### Workers to cover

| Worker | Status | Complexity | What to test |
|--------|--------|-----------|-------------|
| `crawl_website.py` | Partial | High | Full crawl orchestration: URL discovery, page fetching, progress commits, ingest dispatch ordering. Extend existing indirect coverage. |
| `ingest_document.py` | Partial | High | Full ingestion pipeline: extraction, chunking, embedding, status transitions, autoconfig trigger. Extend `test_ingest_completion_check`. |
| `run_autoconfig.py` | Partial | Medium | Extend existing 3 tests: error paths, LLM mock failures, concurrent execution guard |
| `deliver_webhook.py` | Partial | Medium | Extend retry logic tests: full delivery cycle, HTTP error handling, payload signing |
| `send_report.py` | Partial | Medium | Extend existing 9 tests: scheduling edge cases, provider failures |
| `analyze_conversation.py` | None | Medium | Sentiment scoring, topic extraction, DB writes |
| `cluster_gaps.py` | None | Medium | Gap clustering logic, threshold behavior |
| `compute_sentiment_trends.py` | None | Low | Trend aggregation, date range handling |
| `generate_qa.py` | None | Medium | Q&A generation from doc content, LLM mock |
| `close_stale_conversations.py` | None | Low | Staleness detection, status transitions |
| `auto_recharge.py` | None | Low | Threshold check, credit top-up, self-hosted skip |
| `gdpr_export.py` | None | Medium | Data collection, archive creation, cleanup |
| `purge_old_data.py` | None | Low | Retention policy enforcement, cascade deletes |
| `sync_documents.py` | None | Medium | External source sync, diff detection |
| `reindex_article.py` | None | Low | Re-embedding, chunk replacement |

### Worker testing pattern

Workers wrap async code in `asyncio.run()`. Tests call the async `_run()` function directly — no Celery broker needed. Mock DB session and external calls (LLM, Stripe, HTTP).

```python
async def test_analyze_conversation_scores_sentiment():
    """Test the async inner function directly, mock LLM response."""
    with patch("app.services.llm.get_llm_client") as mock_llm:
        mock_llm.return_value.generate.return_value = '{"sentiment": 0.8, "topics": ["billing"]}'
        result = await _run(conversation_id=str(uuid4()))
        assert result["sentiment"] == 0.8
```

### Implementation grouping

This phase is too large for a single plan. Split into:

- **1a:** `resolution_service` + RAG pipeline (~40-50 tests)
- **1b:** Remaining 8 services (~50-60 tests)
- **1c:** All workers (~70-80 tests, includes extending partial coverage)

### Factory extensions

New test factories needed for this phase: `make_article()`, `make_qa_pair()`, `make_action()`, `make_webhook_config()`, `make_crawl_job()` (if not already in factories). Add to `backend/tests/factories.py`.

### Deliverable

- ~160-200 new unit tests
- Coverage gate raised to **70%**
- Workers included in coverage (remove `app/workers/tasks/*` from `pyproject.toml` omit)

## Phase 2: Backend Integration Tests — Fill Route Gaps

Test every API route group that currently has zero integration tests. Uses `auth_client` fixture (httpx AsyncClient with valid JWT) hitting real DB via savepoint rollback.

### Route groups needing integration tests

| Route Group | Status | What to test |
|-------------|--------|-------------|
| `actions.py` | None | Action CRUD, execution, workspace scoping |
| `articles.py` | None | Create, list, get, update, delete — workspace scoping |
| `billing.py` | None | Checkout/portal/webhook — both cloud and self-hosted modes. Mock Stripe. Webhook returns 200 in self-hosted. |
| `chat.py` | None | Authenticated chat initiation, message history, SSE streaming |
| `config.py` | None | Deployment config — returns correct `cloud_mode` value |
| `copilot.py` | None | Copilot message, tool calls, streaming |
| `documents.py` | None | Document upload, content retrieval, status, deletion |
| `gaps.py` | None | Gap list, detail, clustering trigger |
| `gdpr.py` | None | Request export, poll status, request deletion |
| `integrations.py` | None | Integration config CRUD (email, Slack, etc.) |
| `intelligence.py` | None | Intelligence config, feature gating by plan |
| `invites.py` | None | Create invite, accept, revoke, list |
| `logs.py` | None | Task logs, filtering, pagination |
| `oauth.py` | None | Google Drive, Notion, Slack, Shopify callback handling |
| `onboarding.py` | None | Step progression, completion, skip |
| `public_chat.py` | None | Public widget chat, rate limiting, origin check |
| `qa.py` | None | Q&A pair CRUD |
| `realtime.py` | None | Internal emit — auth via internal secret |
| `two_fa.py` | None | TOTP setup, verify code, disable, login with 2FA |
| `webhooks.py` | None | Incoming Meta/Slack webhook handling, signature verification |
| `widget_config.py` | None | Widget config CRUD, public retrieval without auth |
| `workspaces.py` | None | Workspace CRUD, member management, settings |

Note: Some of these have unit-level tests in `tests/unit/` (e.g., `test_logs_endpoints.py`, `test_copilot_endpoint.py`), but no integration tests that exercise the full route → service → DB path.

### Tenant isolation expansion

Current IDOR tests cover ~28 scenarios. Extend to cover every new route group. Pattern:

```python
async def test_articles_idor(auth_client, second_workspace):
    """Workspace B cannot access Workspace A's articles."""
    resp = await auth_client.get(f"/api/v1/workspaces/{second_workspace.id}/articles")
    assert resp.status_code == 403
```

### Implementation grouping

22 route groups is too large for a single plan. Split into:

- **2a:** Core routes — chatbots (extend), workspaces, documents, chat, public_chat, crawl (extend), knowledge_bases (extend) (~80-100 tests)
- **2b:** Remaining routes — articles, actions, billing, copilot, config, gaps, gdpr, integrations, intelligence, invites, logs, oauth, onboarding, qa, realtime, two_fa, webhooks, widget_config (~100-120 tests)

### Factory extensions

Additional factories needed: `make_invite()`, `make_gdpr_request()`, `make_integration_config()`, `make_widget_config()`. Add to `backend/tests/factories.py`.

### Deliverable

- ~180-220 new integration tests
- Tenant isolation coverage for all route groups
- Coverage gate raised to **80%**

## Phase 3: Contract Tests — Lock Down API Schemas

Validate every endpoint's response shape against a JSON Schema contract. If a field is renamed, removed, or its type changes, the test fails before it reaches consumers.

### Approach

- New `backend/tests/contract/` directory
- One file per route group (e.g., `test_chatbots_contract.py`)
- Uses `jsonschema` library to validate response bodies
- Tests cover success responses AND error responses (400, 404, 422 shapes)
- Schemas defined inline in test files (co-located with assertions)

### Scope

Every route group:
- Auth, workspaces, chatbots, knowledge bases, documents, articles, conversations, crawl, dashboard, logs, intelligence, gaps, billing, credits, integrations, webhooks, copilot, QA, onboarding, GDPR, widget config, public chat, config/deployment

### Public endpoints get extra attention

| Endpoint | Contract coverage |
|----------|------------------|
| `POST /api/v1/public/chat` | SSE event shapes: `token`, `done` (with metadata), `error`. Requires parsing the SSE stream into individual events and validating each event's JSON payload — use a helper that reads `text/event-stream` response and yields parsed `{event, data}` dicts. |
| `GET /api/v1/widget/{chatbot_id}/config` | Widget config envelope (consumed by external embed script) |
| Stripe webhook handler | Incoming event shape validation |
| Slack/Meta webhook handlers | Incoming payload shape validation |
| Outgoing webhook deliveries | Outgoing payload shapes for each event type |

### CI integration

New CI job `contract-tests` runs after `backend-tests`:

```
lint → backend-tests → contract-tests → e2e
```

### Deliverable

- ~80-100 contract tests
- New `backend/tests/contract/` directory
- New CI job
- Coverage gate stays at **80%**

## Phase 4: Frontend Tests — Component Coverage + Store Hardening

Fill the gap between store/API unit tests and E2E. Fast component-level tests using Vitest + `@testing-library/react`.

### Component tests (new)

| Category | What to test |
|----------|-------------|
| Page rendering | Each dashboard page renders without crash, shows loading states, displays data from mocked API |
| Forms | Validation rules, submit behavior, error display, field interactions |
| Modals/dialogs | Open/close, confirm/cancel, form submission within modal |
| Tables | Sorting, filtering, pagination, empty state |
| Error boundaries | Fallback UI on component crash |

### Store hardening

| Store | What to test |
|-------|-------------|
| `useChatbotStore` | Patch sync between `currentChatbot` and `chatbots[]`, edge cases |
| `useDeploymentStore` | Cloud vs self-hosted conditional behavior, loading state |
| `useWorkspaceStore` | Workspace switching, membership edge cases |

### Hook tests

| Hook | What to test |
|------|-------------|
| `useKeyboardShortcuts` | Key binding registration, cleanup, conflict handling |
| `useActivityConsole` | Event processing, auto-dismiss timing |
| `useRealtimeNotifications` | Event subscription, toast triggers |

### Coverage expansion

Expand Vitest coverage config to include:
- `src/components/**` (currently excluded)
- `src/app/**` (currently excluded)
- Keep excluding `src/lib/sse.ts`

### Deliverable

- ~100-120 new frontend tests
- Frontend coverage gate introduced: **80%**

## Phase 5: E2E — Critical User Journeys

Expand Playwright E2E from 4 flows to 12, covering every major user journey.

### New E2E flows

| Flow | Steps | Async? |
|------|-------|--------|
| **Crawl → Chatbot ready** | Paste URL → crawl starts → docs ingest → autoconfig → chatbot ready | Yes (polling) |
| **Public chat widget** | Load widget → send message → receive response → conversation in admin logs | Yes (SSE) |
| **Knowledge base management** | Create KB → upload doc → wait for indexing → verify chunks → delete | Yes (polling) |
| **Settings flows** | LLM config → save key → intelligence settings → email integration | No |
| **Team management** | Invite → accept → verify access → change role → remove | No |
| **GDPR** | Request export → download → request deletion → verify removed | Yes (polling) |
| **Billing (cloud mode)** | View plans → checkout (mocked Stripe) → upgrade reflected | No (skip if self-hosted) |
| **Two-factor auth** | Enable TOTP → verify code → login with 2FA → disable | No |

### Infrastructure

- Each flow gets its own test file in `frontend/e2e/`
- Async flows use polling with timeouts (no fixed `sleep`)
- Billing E2E tests skip when `CLOUD_MODE=false`
- Keep single-worker Playwright config
- 2 retries in CI, 0 in local dev (existing config)

### Deliverable

- ~40-50 new E2E tests across 8 new test files
- E2E tests provide confidence but do NOT contribute to pytest/Vitest coverage numbers

## Phase 6: CI Hardening + Final Gate

Infrastructure-only phase. No new tests. Tie everything together.

### Coverage gate progression

| Phase | Backend | Frontend | Notes |
|-------|---------|----------|-------|
| 0 | 45% | — | Fix existing failures |
| 1 | 70% | — | Workers included in coverage |
| 2 | 80% | — | Split into 2a/2b |
| 3 | 85% | — | Contract tests add incremental coverage |
| 4 | 90% | 90% | Frontend gate introduced at final target |
| 5 | 90% | 90% | E2E adds confidence, not coverage numbers |

Note: E2E (Playwright) tests run against a live stack and do not contribute to pytest or Vitest coverage reports. The 90% gate must be achievable from unit + integration + contract tests (Phases 1-4). The expanded scope in Phases 1 and 2 (workers, all route groups) makes this realistic.

### CI pipeline (final)

```
lint → backend-tests (90%) → contract-tests → e2e
lint → frontend-tests (90%) → e2e
backend-tests → schema-perf
```

### Changes

| Change | Detail |
|--------|--------|
| Workers in coverage | Remove `app/workers/tasks/*` from `pyproject.toml` omit |
| Frontend coverage gate | Add `--coverage --coverage.thresholds.lines=90` to Vitest CI |
| Test DB migration automation | CI step runs `alembic upgrade head` against `pulse_test` explicitly |
| New Makefile targets | `make test-contract`, `make test-all-gates` |
| Contract tests CI job | New job between backend-tests and e2e |

### Makefile additions

```makefile
test-contract:
	docker compose exec backend pytest tests/contract/ -v

test-all-gates:
	$(MAKE) test-coverage-gate
	$(MAKE) test-contract
	$(MAKE) test-frontend-coverage
```

### Deliverable

- Updated CI pipeline
- Updated Makefile
- Updated coverage config
- 90% enforced on both backend and frontend

## Implementation Order

Each phase becomes its own spec → plan → implementation cycle:

1. **Phase 0** — Green baseline (1 cycle, small)
2. **Phase 1a** — Resolution service + RAG pipeline unit tests (1 cycle)
3. **Phase 1b** — Remaining service unit tests (1 cycle)
4. **Phase 1c** — Worker unit tests (1 cycle)
5. **Phase 2a** — Core route integration tests (1 cycle)
6. **Phase 2b** — Remaining route integration tests (1 cycle)
7. **Phase 3** — Contract tests (1 cycle)
8. **Phase 4** — Frontend component tests (1 cycle)
9. **Phase 5** — E2E expansion (1 cycle)
10. **Phase 6** — CI hardening (1 cycle, small)

Total: 7 phases, 10 implementation cycles.

## Scope Exclusions

- Visual regression testing (screenshot comparison)
- Performance benchmarking beyond existing k6 setup
- Mutation testing
- Browser compatibility testing
- Mobile responsiveness testing
- Accessibility auditing (could be a separate initiative)
- Load testing expansion beyond existing k6 scripts
