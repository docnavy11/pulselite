# Comprehensive Testing Strategy — Design Spec

## Overview

A bottom-up, phased testing strategy to bring PulseLite from 45% coverage with 32 broken tests to 90%+ enforced coverage across backend (including workers), frontend, contract tests, and E2E — suitable for an open-source product with a commercial offering.

**Approach:** Layer-by-layer through the test pyramid. Each phase produces a self-contained improvement with a progressive coverage gate ramp (45% → 70% → 80% → 90%).

**Scope:** 7 phases, estimated 6-8 implementation cycles.

## Current State

- **573 total tests** (386 backend, 187 frontend)
- **32 pre-existing failures** (13 backend, 19 frontend)
- **Coverage gate:** 45% backend, none frontend
- **Workers excluded** from coverage
- **9 services** with zero unit tests
- **8+ route groups** with zero integration tests
- **No contract tests**
- **4 E2E flows** (auth, chatbots, dashboard, conversations)

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
| `webhook_service.py` | Medium | Low | Webhook config CRUD |

### Untested workers

| Worker | Complexity | What to test |
|--------|-----------|-------------|
| `analyze_conversation.py` | Medium | Sentiment scoring, topic extraction, DB writes |
| `cluster_gaps.py` | Medium | Gap clustering logic, threshold behavior |
| `compute_sentiment_trends.py` | Low | Trend aggregation, date range handling |
| `generate_qa.py` | Medium | Q&A generation from doc content, LLM mock |
| `close_stale_conversations.py` | Low | Staleness detection, status transitions |
| `auto_recharge.py` | Low | Threshold check, credit top-up, self-hosted skip |
| `gdpr_export.py` | Medium | Data collection, archive creation, cleanup |
| `purge_old_data.py` | Low | Retention policy enforcement, cascade deletes |
| `sync_documents.py` | Medium | External source sync, diff detection |
| `reindex_article.py` | Low | Re-embedding, chunk replacement |

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
- **1c:** All workers (~50-60 tests)

### Deliverable

- ~150-200 new unit tests
- Coverage gate raised to **70%**
- Workers included in coverage (remove `app/workers/tasks/*` from `pyproject.toml` omit)

## Phase 2: Backend Integration Tests — Fill Route Gaps

Test every API route group that currently has zero integration tests. Uses `auth_client` fixture (httpx AsyncClient with valid JWT) hitting real DB via savepoint rollback.

### Untested route groups

| Route Group | Endpoints | What to test |
|-------------|----------|-------------|
| `articles.py` | CRUD | Create, list, get, update, delete — workspace scoping |
| `gdpr.py` | Export/delete | Request export, poll status, request deletion |
| `two_fa.py` | TOTP setup/verify | Enable, verify code, disable, login with 2FA |
| `oauth.py` | Callbacks | Google Drive, Notion, Slack, Shopify callback handling |
| `onboarding.py` | Step progression | Step update, completion, skip |
| `config.py` | Deployment config | Returns correct `cloud_mode` value |
| `gaps.py` | Gap list/detail | List, detail, clustering trigger |
| `widget_config.py` | Widget CRUD + public | Config CRUD, public retrieval without auth |
| `intelligence.py` | Config + features | Intelligence config, feature gating by plan |
| `qa.py` | Q&A CRUD | Create, list, update, delete pairs |
| `billing.py` | Checkout/portal/webhook | Both cloud and self-hosted modes. Mock Stripe. Webhook returns 200 in self-hosted. |
| `realtime.py` | Internal emit | Auth via internal secret, event emission |

### Tenant isolation expansion

Current IDOR tests cover ~28 scenarios. Extend to cover every new route group. Pattern:

```python
async def test_articles_idor(auth_client, second_workspace):
    """Workspace B cannot access Workspace A's articles."""
    resp = await auth_client.get(f"/api/v1/workspaces/{second_workspace.id}/articles")
    assert resp.status_code == 403
```

### Deliverable

- ~100-120 new integration tests
- Tenant isolation coverage for all new route groups
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
| `POST /api/v1/public/chat` | SSE event shapes: `token`, `done` (with metadata), `error` |
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
- Coverage gate raised to **90%** (final target)

## Phase 6: CI Hardening + Final Gate

Infrastructure-only phase. No new tests. Tie everything together.

### Coverage gate progression

| Phase | Backend | Frontend |
|-------|---------|----------|
| 0 | 45% | — |
| 1 | 70% | — |
| 2 | 80% | — |
| 3 | 80% | — |
| 4 | 80% | 80% |
| 5 | 90% | 90% |

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
5. **Phase 2** — Integration tests (1 cycle)
6. **Phase 3** — Contract tests (1 cycle)
7. **Phase 4** — Frontend component tests (1 cycle)
8. **Phase 5** — E2E expansion (1 cycle)
9. **Phase 6** — CI hardening (1 cycle, small)

## Scope Exclusions

- Visual regression testing (screenshot comparison)
- Performance benchmarking beyond existing k6 setup
- Mutation testing
- Browser compatibility testing
- Mobile responsiveness testing
- Accessibility auditing (could be a separate initiative)
- Load testing expansion beyond existing k6 scripts
