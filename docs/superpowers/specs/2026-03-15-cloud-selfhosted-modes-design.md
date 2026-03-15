# Cloud vs Self-Hosted Deployment Modes — Design Spec

## Overview

PulseLite supports two deployment modes controlled by a single env var `CLOUD_MODE`:

- **Cloud** (`CLOUD_MODE=true`): Full SaaS with billing, credit system, plan tiers, BYOK pricing. Two sub-modes:
  - **Platform keys**: workspace uses PulseLite's LLM API keys, pays full credit price.
  - **BYOK**: workspace brings their own OpenRouter key, pays 50% credit price.
- **Self-hosted** (`CLOUD_MODE=false`, default): All features unlocked, no billing/credit system, no plan limits. User manages their own LLM keys.

## 1. Config & Mode Detection

### Backend

**`backend/app/config.py`** — add to `Settings`:
```python
CLOUD_MODE: bool = False
```

**`backend/app/services/deployment.py`** — new file:
```python
from app.config import settings

def is_cloud() -> bool:
    return settings.CLOUD_MODE

def is_self_hosted() -> bool:
    return not settings.CLOUD_MODE
```

**`.env.example`** — add:
```
CLOUD_MODE=false
```

### Frontend

**New public endpoint** `GET /api/v1/config/deployment` (no auth):
```json
{ "cloud_mode": true }
```

**Pydantic schema** in `backend/app/schemas/config.py`:
```python
class DeploymentConfigResponse(BaseModel):
    cloud_mode: bool
```

**New file `frontend/src/stores/deployment-store.ts`** — Zustand store:
- `isCloud: boolean` — fetched once at app init
- `isLoaded: boolean` — prevents flash of cloud UI before config is loaded
- `useDeploymentStore(s => s.isCloud)` used by components for conditional rendering
- Called in `App.tsx` root component before rendering routes. Components treat `isLoaded=false` as loading state to avoid flashing billing links.

**Route:** registered in `main.py`, defined in new `backend/app/api/v1/config.py`.

**Chat widget:** does not call this endpoint, remains unaware of mode.

## 2. BYOK Flag & Workspace Model

### Data model

**`backend/app/models/organizational.py`** — add to `Workspace`:
```python
is_byok: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)
```

### Semantics

| Mode | `is_byok` | Behavior |
|------|-----------|----------|
| Cloud | `false` | Platform LLM keys used, full credit pricing |
| Cloud | `true` | Workspace's own OpenRouter key used, 50% credit pricing |
| Self-hosted | ignored | No credits charged, user manages own keys |

### Onboarding (cloud mode only)

During workspace creation, a step asks: "Use our AI models, or bring your own API key?"
- "Use ours" → `is_byok=false`, shown credit pricing
- "Bring my own" → `is_byok=true`, prompted for OpenRouter key, shown 50% pricing

Self-hosted onboarding skips this step entirely.

### LLM settings page

- **Cloud mode:** toggle between BYOK and platform-provided, pricing difference displayed.
- **Self-hosted:** API key fields only (no BYOK toggle, no pricing info).

## 3. Credit Deduction Wiring

### New integration required

Credit deduction does not currently exist in the chat flow — this is net-new work. The LLM clients also do not currently surface token usage metadata. Changes needed:

1. **LLM clients** (`openai_client.py`, `openrouter_client.py`, etc.): After streaming completes, return `prompt_tokens` + `completion_tokens` from the provider's response metadata (OpenAI/OpenRouter APIs include `usage` in the final streamed chunk).
2. **`resolution_service.py`**: Capture token counts from the LLM client response and pass them to the credit deduction logic.

### Where deduction happens

In `backend/app/services/resolution_service.py`, after the LLM streaming response completes and token counts are available.

Call sequence:
1. `estimate_token_cost(model, total_tokens, is_byok=workspace.is_byok)` — returns credit cost (applies 50% discount if BYOK). This function lives in `backend/app/services/credits.py`.
2. Atomically decrement `workspace.credit_balance`
3. Write `CreditLedger` entry with reason, model, tokens, cost, balance_after

### Pre-chat balance check

Before starting a response (cloud mode only), check `workspace.credit_balance > 0`. If exhausted, return SSE error event:
```json
{"type": "error", "detail": "Credit balance exhausted"}
```

### Self-hosted

All credit checks and deductions skipped entirely. `is_cloud()` guard wraps the billing logic.

### Existing infrastructure reused

- `CreditLedger` table — already exists
- `estimate_token_cost()` in `backend/app/services/credits.py` — already exists, add `is_byok` parameter
- `workspace.credit_balance` — already exists

## 4. Configurable Plan Tiers

### New model: `PlanTier`

**`backend/app/models/plan_tier.py`**:

| Column | Type | Description |
|--------|------|-------------|
| `slug` | String(32), PK | e.g. `free`, `starter`, `growth`, `professional`, `agency`, `enterprise` |
| `name` | String(64) | Display name |
| `price_monthly_cents` | Integer | Price in cents (0 for free) |
| `max_chatbots` | Integer | -1 = unlimited |
| `max_conversations_monthly` | Integer | -1 = unlimited |
| `max_knowledge_bases` | Integer | -1 = unlimited |
| `max_chars_indexed` | BigInteger | -1 = unlimited |
| `features` | JSONB | List of feature slugs: `["intelligence", "reranking", "email_reports"]` |

### Seed data

**Note on existing plan inconsistency:** The codebase currently has conflicting plan definitions:
- `PLAN_LIMITS` and `PLAN_PRICES` in `billing.py`: `free`, `starter`, `growth`, `professional`, `agency`, `enterprise` (6 slugs)
- `PLAN_CHAR_LIMITS` in `config.py`: `free`, `starter`, `growth`, `enterprise` (4 slugs)
- `BILLING_PLANS` in `api/v1/billing.py`: `free`, `starter`, `growth`, `enterprise` (4 slugs)

The canonical set for the `plan_tiers` table includes all 6 slugs to avoid breaking any existing workspace:

| Slug | Price | Chatbots | Conv/mo | KBs | Chars | Features |
|------|-------|----------|---------|-----|-------|----------|
| `free` | $0 | 1 | 100 | 2 | 500K | `[]` |
| `starter` | $49 | 3 | 1K | 10 | 2M | `["email_reports"]` |
| `growth` | $149 | 10 | 10K | 50 | 10M | `["intelligence", "reranking", "email_reports"]` |
| `professional` | $149 | 10 | 10K | 50 | 10M | `["intelligence", "reranking", "email_reports"]` |
| `agency` | $499 | 50 | 50K | 200 | unlimited | `["intelligence", "reranking", "email_reports"]` |
| `enterprise` | custom | unlimited | unlimited | unlimited | unlimited | `["intelligence", "reranking", "email_reports", "priority_support"]` |

`growth` and `professional` are treated as equivalent tiers (same limits). The migration includes an Alembic data migration to normalize existing `workspace.plan` values: `UPDATE workspaces SET plan = 'growth' WHERE plan = 'professional'`. Going forward, only `growth` is used in `BILLING_PLANS` and Stripe mappings; `professional` remains in the table as a legacy alias for safety.

### Migration strategy for hardcoded references

Four separate locations define plan data today — all must be replaced:
1. `PLAN_LIMITS` in `backend/app/services/billing.py` — conversation/chatbot/KB limits
2. `PLAN_CHAR_LIMITS` in `backend/app/config.py` — character indexing limits
3. `BILLING_PLANS` in `backend/app/api/v1/billing.py` — public plan metadata
4. `PLAN_PRICES` / `PLAN_PRICES_ANNUAL` in `billing.py` — Stripe price ID mappings

After the `plan_tiers` table is seeded, all four dicts are replaced with lookups via a cached helper.

### Plan tier lookup helper

**`backend/app/services/plan_service.py`** — new file:
```python
def get_plan_tier(slug: str) -> PlanTier
def get_plan_limits(slug: str) -> dict
def has_feature(workspace: Workspace, feature: str) -> bool
```

`get_plan_tier()` reads from an in-memory cache loaded at startup, keyed by slug. Returns the `enterprise` tier as fallback for unknown slugs.

`has_feature()` looks up the workspace's plan tier and checks if `feature` is in the tier's `features` list. In self-hosted mode, always returns `True`.

### Usage

Replace all references to hardcoded plan dicts with calls to `plan_service` functions.

**Self-hosted:** Plan tiers table exists but is never consulted. All limits treated as unlimited, all features enabled.

### Workspace.plan FK

`Workspace.plan` remains a free-text string (no FK to `plan_tiers.slug`). Lookup is application-level via `get_plan_tier()`. Unknown/stale plan values fall back to `enterprise` tier limits — this is safe because the only way `plan` is set is via Stripe webhook handling, which maps price IDs to known slugs.

## 5. Feature Gating & Cloud-Only Hiding

### Backend: `require_cloud` dependency

**`backend/app/services/deployment.py`** — add:
```python
from fastapi import HTTPException

async def require_cloud():
    if is_self_hosted():
        raise HTTPException(status_code=404)
```

Applied as `Depends(require_cloud)` on:
- All `/billing/*` routes (including `GET /billing/plans` — currently listed as a public exception in CLAUDE.md, must be updated)
- All `/credits/*` routes

**Exception:** The Stripe webhook endpoint (`POST /billing/webhook`) must return HTTP 200 with an empty body in self-hosted mode, not 404. Per CLAUDE.md: "All webhook endpoints must return HTTP 200 even on malformed input." Stripe retries on non-2xx and would eventually disable the endpoint. Add a `cloud_or_200` guard in `deployment.py` that returns `Response(status_code=200)` early when self-hosted, and apply it to the webhook route instead of `require_cloud`.

### Backend: gated behavior

| Feature | Cloud | Self-hosted |
|---------|-------|-------------|
| Credit deduction on chat | Active | Skipped |
| Pre-chat balance check | Active | Skipped |
| Conversation cap enforcement | Active | Skipped |
| Character limit enforcement | Active | Skipped |
| Auto-recharge worker task | Runs | Skips execution |
| Stripe webhook handler | Active | Returns 200 (no-op) |
| Plan tier lookups | Active | Returns unlimited |

### Frontend: hidden in self-hosted mode

| Element | Cloud | Self-hosted |
|---------|-------|-------------|
| Billing settings page | Visible | Hidden from sidebar + routes |
| Credits display & history | Visible | Hidden |
| Auto-recharge config | Visible | Hidden |
| BYOK toggle (LLM settings) | Visible | Hidden |
| Plan upgrade prompts | Visible | Hidden |
| Usage/cost breakdown | Visible | Hidden |

### Frontend: visible in both modes

All chatbot/conversation/KB features, intelligence suite, LLM settings (key fields), email/integrations, webhooks, data retention, security, team, worker health.

### Admin panel indicator

Sidebar footer shows a small badge: "Self-Hosted" or "Cloud". Not shown in the chat widget.

## 6. Conversation Cap Enforcement

### Cloud mode

In `backend/app/services/conversation_service.py`, before creating a new conversation:
1. Look up workspace's plan tier → `max_conversations_monthly`
2. If `-1` (unlimited), skip check
3. Count conversations created this calendar month for the workspace
4. If `>= max_conversations_monthly`, reject with HTTP 429: "Monthly conversation limit reached"

The public chat endpoint (`POST /api/v1/public/chat`) must also respect this — the cap applies to end-user widget conversations, not just admin-created ones.

### Self-hosted

No cap — check skipped entirely via `is_cloud()` guard.

## 7. Migration & File Summary

### New Alembic migration

1. Add `is_byok` boolean column to `workspaces` table (default `false`)
2. Create `plan_tiers` table with seed data (6 rows)
3. Normalize workspace plan values: `UPDATE workspaces SET plan = 'growth' WHERE plan = 'professional'`

### New files

| File | Purpose |
|------|---------|
| `backend/app/services/deployment.py` | `is_cloud()`, `is_self_hosted()`, `require_cloud` dependency |
| `backend/app/services/plan_service.py` | `get_plan_tier()`, `get_plan_limits()`, `has_feature()` with cache |
| `backend/app/models/plan_tier.py` | `PlanTier` model |
| `backend/app/schemas/config.py` | `DeploymentConfigResponse` schema |
| `backend/app/api/v1/config.py` | Public deployment config endpoint |
| `frontend/src/stores/deployment-store.ts` | Zustand store for deployment mode |

### Key modified files

| File | Change |
|------|--------|
| `backend/app/config.py` | Add `CLOUD_MODE` setting |
| `backend/app/models/organizational.py` | Add `is_byok` to Workspace |
| `backend/app/models/__init__.py` | Register `PlanTier` |
| `backend/app/main.py` | Register config router |
| `backend/app/services/resolution_service.py` | Credit deduction after LLM response, pre-chat balance check |
| `backend/app/services/credits.py` | BYOK discount in `estimate_token_cost()` |
| `backend/app/services/billing.py` | Replace hardcoded `PLAN_LIMITS`/`PLAN_PRICES` with `plan_service` lookups |
| `backend/app/services/conversation_service.py` | Conversation cap enforcement |
| `backend/app/services/ingestion/pipeline.py` | Replace `PLAN_CHAR_LIMITS` with `plan_service` lookup, gate by `is_cloud()` |
| `backend/app/services/chatbot_service.py` | Replace `PLAN_CHAR_LIMITS` with `plan_service` lookup, gate by `is_cloud()` |
| `backend/app/api/v1/workspaces.py` | Replace `PLAN_CHAR_LIMITS` with `plan_service` lookup, gate by `is_cloud()` |
| `backend/app/workers/tasks/auto_recharge.py` | Skip execution if self-hosted |
| `backend/app/api/v1/billing.py` | Add `require_cloud` dependency, replace `BILLING_PLANS` with DB lookup |
| `backend/app/services/llm/openai_client.py` | Surface token usage from streaming response |
| `backend/app/services/llm/openrouter_client.py` | Surface token usage from streaming response |
| `CLAUDE.md` | Update public exceptions list (remove `GET /billing/plans` for self-hosted) |
| `frontend/src/components/layout/Sidebar.tsx` | Mode badge, conditional billing link |
| `frontend/src/app/(dashboard)/settings/llm/page.tsx` | Conditional BYOK toggle |
| `frontend/src/App.tsx` | Conditional billing route, deployment config fetch |
| `frontend/src/lib/types.ts` | Add `is_byok` to Workspace, deployment config types |
| `frontend/src/lib/api-functions.ts` | Add `getDeploymentConfig()` |

## 8. Testing

### Backend

| Test | What it verifies |
|------|-----------------|
| `test_deployment.py` | `is_cloud()` / `is_self_hosted()` return correct values based on `CLOUD_MODE` setting |
| `test_deployment.py` | `require_cloud` raises 404 when `CLOUD_MODE=false` |
| `test_credits.py` | `estimate_token_cost()` applies 50% discount when `is_byok=True` |
| `test_plan_service.py` | `get_plan_tier()` returns correct tier, falls back to enterprise for unknown slugs |
| `test_plan_service.py` | `has_feature()` returns True for all features in self-hosted mode |
| `test_conversation_cap.py` | Conversation cap enforced in cloud mode, skipped in self-hosted |
| `test_config_endpoint.py` | `GET /config/deployment` returns correct `cloud_mode` value |

**Test fixture:** Override `settings.CLOUD_MODE` per test using `monkeypatch` or a fixture that toggles the setting. Reset after each test to avoid cross-contamination.

### Frontend

| Test | What it verifies |
|------|-----------------|
| `deployment-store.test.ts` | Store initializes from API, `isCloud` reflects response |
| Sidebar render test | Billing link hidden when `isCloud=false` |

## 9. Scope Exclusions

The following are explicitly out of scope for this design:
- Infrastructure simplification for self-hosted (Redis/Postgres remain required)
- Admin UI for editing plan tiers (tiers are seed data, changeable via migration or direct DB edit)
- Per-feature granular feature flags beyond plan tier `features` JSONB
- Self-hosted licensing/key validation
- Managed cloud deployment tooling (Terraform, Kubernetes manifests)
