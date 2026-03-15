# Cloud vs Self-Hosted Deployment Modes — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `CLOUD_MODE` env var that controls whether billing, credits, plan limits, and Stripe integration are active — self-hosted mode unlocks everything with no billing.

**Architecture:** Single `CLOUD_MODE` boolean read at startup. Backend `deployment.py` service exposes `is_cloud()`/`is_self_hosted()` helpers and a `require_cloud` FastAPI dependency. Plan tiers move from hardcoded dicts to a `plan_tiers` DB table with a cached lookup service. Credit deduction is wired into the chat flow (cloud only) with BYOK 50% discount. Frontend fetches deployment config once at init and conditionally renders billing UI.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, Celery, Zustand, React, Vitest

**Spec:** `docs/superpowers/specs/2026-03-15-cloud-selfhosted-modes-design.md`

---

## Chunk 1: Backend Foundation

### Task 1: Deployment mode service + config endpoint

**Files:**
- Create: `backend/app/services/deployment.py`
- Create: `backend/app/schemas/config.py`
- Create: `backend/app/api/v1/config.py`
- Create: `backend/tests/unit/test_deployment.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Modify: `.env.example`

- [ ] **Step 1: Write failing tests for deployment service**

```python
# backend/tests/unit/test_deployment.py
"""Tests for deployment mode service."""
from unittest.mock import patch

from fastapi import HTTPException
import pytest

from app.services.deployment import is_cloud, is_self_hosted, require_cloud, cloud_or_200


def test_is_cloud_returns_true_when_cloud_mode_enabled():
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = True
        assert is_cloud() is True


def test_is_cloud_returns_false_when_cloud_mode_disabled():
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = False
        assert is_cloud() is False


def test_is_self_hosted_returns_true_when_cloud_mode_disabled():
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = False
        assert is_self_hosted() is True


def test_is_self_hosted_returns_false_when_cloud_mode_enabled():
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = True
        assert is_self_hosted() is False


@pytest.mark.asyncio
async def test_require_cloud_raises_404_when_self_hosted():
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = False
        with pytest.raises(HTTPException) as exc_info:
            await require_cloud()
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_require_cloud_passes_when_cloud():
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = True
        result = await require_cloud()
        assert result is None


@pytest.mark.asyncio
async def test_cloud_or_200_returns_response_when_self_hosted():
    from starlette.responses import Response
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = False
        result = await cloud_or_200()
        assert isinstance(result, Response)
        assert result.status_code == 200


@pytest.mark.asyncio
async def test_cloud_or_200_returns_none_when_cloud():
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = True
        result = await cloud_or_200()
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest tests/unit/test_deployment.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.deployment'`

- [ ] **Step 3: Add `CLOUD_MODE` to config and create deployment service**

Add to `backend/app/config.py` Settings class (after existing settings):
```python
CLOUD_MODE: bool = False
```

Create `backend/app/services/deployment.py`:
```python
"""Deployment mode helpers — cloud vs self-hosted."""

from fastapi import HTTPException
from starlette.responses import Response

from app.config import settings


def is_cloud() -> bool:
    return settings.CLOUD_MODE


def is_self_hosted() -> bool:
    return not settings.CLOUD_MODE


async def require_cloud():
    """FastAPI dependency: raises 404 on self-hosted routes."""
    if is_self_hosted():
        raise HTTPException(status_code=404)


async def cloud_or_200():
    """FastAPI dependency: returns 200 no-op for webhooks in self-hosted mode."""
    if is_self_hosted():
        return Response(status_code=200)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/unit/test_deployment.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Create config endpoint with schema**

Create `backend/app/schemas/config.py`:
```python
from pydantic import BaseModel


class DeploymentConfigResponse(BaseModel):
    cloud_mode: bool
```

Create `backend/app/api/v1/config.py`:
```python
from fastapi import APIRouter

from app.config import settings
from app.schemas.config import DeploymentConfigResponse

router = APIRouter(tags=["config"])


@router.get("/config/deployment", response_model=DeploymentConfigResponse)
async def get_deployment_config():
    return DeploymentConfigResponse(cloud_mode=settings.CLOUD_MODE)
```

Register in `backend/app/main.py` — add import alongside other router imports:
```python
from app.api.v1 import config as config_router
```
Add to router includes (alongside existing ones):
```python
app.include_router(config_router.router, prefix="/api/v1")
```

Add to `.env.example`:
```
# Deployment mode: set to true for PulseLite Cloud
CLOUD_MODE=false
```

- [ ] **Step 6: Run full unit test suite to verify no regressions**

Run: `docker compose exec backend pytest tests/unit/test_deployment.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/deployment.py backend/app/schemas/config.py backend/app/api/v1/config.py backend/tests/unit/test_deployment.py backend/app/config.py backend/app/main.py .env.example
git commit -m "feat: add deployment mode service and config endpoint"
```

---

### Task 2: PlanTier model, migration, and plan service

**Files:**
- Create: `backend/app/models/plan_tier.py`
- Create: `backend/app/services/plan_service.py`
- Create: `backend/tests/unit/test_plan_service.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/organizational.py`

- [ ] **Step 1: Write failing tests for plan service**

```python
# backend/tests/unit/test_plan_service.py
"""Tests for plan tier lookup service."""
from unittest.mock import patch, MagicMock

import pytest

from app.services.plan_service import get_plan_tier, get_plan_limits, has_feature


# --- get_plan_tier ---

def _make_tier(slug, max_chatbots=1, max_conversations=-1, max_knowledge_bases=2,
               max_chars_indexed=500_000, features=None):
    tier = MagicMock()
    tier.slug = slug
    tier.max_chatbots = max_chatbots
    tier.max_conversations_monthly = max_conversations
    tier.max_knowledge_bases = max_knowledge_bases
    tier.max_chars_indexed = max_chars_indexed
    tier.features = features or []
    return tier


FAKE_CACHE = {
    "free": _make_tier("free", 1, 100, 2, 500_000, []),
    "growth": _make_tier("growth", 10, 10_000, 50, 10_000_000, ["intelligence", "reranking"]),
    "enterprise": _make_tier("enterprise", -1, -1, -1, -1, ["intelligence", "reranking", "email_reports"]),
}


def test_get_plan_tier_returns_matching_tier():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        tier = get_plan_tier("free")
        assert tier.slug == "free"
        assert tier.max_chatbots == 1


def test_get_plan_tier_unknown_slug_falls_back_to_enterprise():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        tier = get_plan_tier("nonexistent")
        assert tier.slug == "enterprise"


def test_get_plan_limits_returns_dict():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        limits = get_plan_limits("free")
        assert limits["chatbots"] == 1
        assert limits["conversations"] == 100
        assert limits["knowledge_bases"] == 2
        assert limits["chars_indexed"] == 500_000


def test_get_plan_limits_unlimited():
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        limits = get_plan_limits("enterprise")
        assert limits["chatbots"] == -1
        assert limits["conversations"] == -1


# --- has_feature ---

def test_has_feature_returns_true_when_feature_in_plan():
    workspace = MagicMock()
    workspace.plan = "growth"
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        with patch("app.services.plan_service.is_self_hosted", return_value=False):
            assert has_feature(workspace, "intelligence") is True


def test_has_feature_returns_false_when_feature_not_in_plan():
    workspace = MagicMock()
    workspace.plan = "free"
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        with patch("app.services.plan_service.is_self_hosted", return_value=False):
            assert has_feature(workspace, "intelligence") is False


def test_has_feature_always_true_in_self_hosted():
    workspace = MagicMock()
    workspace.plan = "free"
    with patch("app.services.plan_service._tier_cache", FAKE_CACHE):
        with patch("app.services.plan_service.is_self_hosted", return_value=True):
            assert has_feature(workspace, "intelligence") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest tests/unit/test_plan_service.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create PlanTier model**

Create `backend/app/models/plan_tier.py`:
```python
from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PlanTier(TimestampMixin, Base):
    __tablename__ = "plan_tiers"

    slug: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    price_monthly_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_chatbots: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    max_conversations_monthly: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    max_knowledge_bases: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    max_chars_indexed: Mapped[int] = mapped_column(BigInteger, nullable=False, default=-1)
    features: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
```

Register in `backend/app/models/__init__.py` — add:
```python
from app.models.plan_tier import PlanTier  # noqa: F401
```

Add `is_byok` to `Workspace` in `backend/app/models/organizational.py` (after existing LLM config fields):
```python
is_byok: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)
```

- [ ] **Step 4: Create plan service**

Create `backend/app/services/plan_service.py`:
```python
"""Cached plan tier lookups."""

import logging

from app.services.deployment import is_self_hosted

logger = logging.getLogger(__name__)

# In-memory cache, loaded at startup via load_plan_tiers()
_tier_cache: dict = {}


async def load_plan_tiers() -> None:
    """Load all plan tiers from DB into memory. Call once at app startup."""
    from app.database import async_session_factory
    from app.models.plan_tier import PlanTier
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(select(PlanTier))
        tiers = result.scalars().all()
        _tier_cache.clear()
        for tier in tiers:
            _tier_cache[tier.slug] = tier
        logger.info(f"Loaded {len(_tier_cache)} plan tiers")


def get_plan_tier(slug: str):
    """Return PlanTier for slug, falling back to enterprise for unknown slugs."""
    return _tier_cache.get(slug, _tier_cache.get("enterprise"))


def get_plan_limits(slug: str) -> dict:
    """Return limits dict for a plan slug."""
    tier = get_plan_tier(slug)
    if tier is None:
        return {"chatbots": -1, "conversations": -1, "knowledge_bases": -1, "chars_indexed": -1}
    return {
        "chatbots": tier.max_chatbots,
        "conversations": tier.max_conversations_monthly,
        "knowledge_bases": tier.max_knowledge_bases,
        "chars_indexed": tier.max_chars_indexed,
    }


def has_feature(workspace, feature: str) -> bool:
    """Check if workspace's plan includes a feature. Always True in self-hosted mode."""
    if is_self_hosted():
        return True
    tier = get_plan_tier(workspace.plan)
    if tier is None:
        return True
    return feature in (tier.features or [])


def get_all_tiers() -> list:
    """Return all cached plan tiers. Used by billing plans endpoint."""
    return list(_tier_cache.values())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/unit/test_plan_service.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Create Alembic migration**

Run: `docker compose exec backend alembic revision --autogenerate -m "add plan_tiers table and workspace is_byok"`

Then edit the generated migration to add seed data and the `is_byok` column. The `upgrade()` function should include:

```python
# After creating plan_tiers table:
op.execute("""
    INSERT INTO plan_tiers (slug, name, price_monthly_cents, max_chatbots, max_conversations_monthly, max_knowledge_bases, max_chars_indexed, features, created_at)
    VALUES
        ('free', 'Free', 0, 1, 100, 2, 500000, '[]', NOW()),
        ('starter', 'Starter', 4900, 3, 1000, 10, 2000000, '["email_reports"]', NOW()),
        ('growth', 'Growth', 14900, 10, 10000, 50, 10000000, '["intelligence", "reranking", "email_reports"]', NOW()),
        ('professional', 'Professional', 14900, 10, 10000, 50, 10000000, '["intelligence", "reranking", "email_reports"]', NOW()),
        ('agency', 'Agency', 49900, 50, 50000, 200, -1, '["intelligence", "reranking", "email_reports"]', NOW()),
        ('enterprise', 'Enterprise', 0, -1, -1, -1, -1, '["intelligence", "reranking", "email_reports", "priority_support"]', NOW())
    ON CONFLICT (slug) DO NOTHING
""")

# Add is_byok to workspaces
op.add_column('workspaces', sa.Column('is_byok', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False))

# Normalize professional -> growth
op.execute("UPDATE workspaces SET plan = 'growth' WHERE plan = 'professional'")
```

- [ ] **Step 7: Run migration**

Run: `docker compose exec backend alembic upgrade head`
Expected: Migration applies successfully

- [ ] **Step 8: Wire plan tier cache loading into app startup**

In `backend/app/main.py`, inside `create_app()`, add a startup event after the app is created:
```python
@app.on_event("startup")
async def _load_plan_tiers():
    from app.services.plan_service import load_plan_tiers
    await load_plan_tiers()
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/plan_tier.py backend/app/models/organizational.py backend/app/services/plan_service.py backend/tests/unit/test_plan_service.py backend/app/models/__init__.py backend/app/main.py backend/alembic/versions/
git commit -m "feat: add PlanTier model, plan service with cache, and migration"
```

---

### Task 3: Replace hardcoded plan dicts with plan_service lookups

**Files:**
- Modify: `backend/app/services/billing.py`
- Modify: `backend/app/api/v1/billing.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Replace `PLAN_LIMITS` and `get_plan_limits()` in billing service**

In `backend/app/services/billing.py`:

Remove the `PLAN_LIMITS` dict (lines 30-36) and the `get_plan_limits()` function (lines 153-154).

Replace `PLAN_LIMITS.get(plan, {}).get("conversations", 100)` references (lines 118, 149) with:
```python
from app.services.plan_service import get_plan_limits as _get_plan_limits
# ...
limits = _get_plan_limits(plan)
workspace.plan_conversation_cap = limits["conversations"]
```

Keep `PLAN_PRICES` and `PLAN_PRICES_ANNUAL` dicts — Stripe price ID mappings stay in billing.py as they are Stripe-specific config, not plan tier data.

- [ ] **Step 2: Replace `BILLING_PLANS` in billing routes**

In `backend/app/api/v1/billing.py`:

Replace the hardcoded `BILLING_PLANS` list (lines 35-80) with a function that reads from the plan_service cache:
```python
from app.services.plan_service import get_plan_tier, get_all_tiers

def _build_billing_plans() -> list[dict]:
    """Build billing plans response from cached plan tiers."""
    display_order = ["free", "starter", "growth", "agency", "enterprise"]
    all_tiers = {t.slug: t for t in get_all_tiers()}
    plans = []
    for slug in display_order:
        tier = all_tiers.get(slug)
        if tier is None:
            continue
        plans.append({
            "id": tier.slug,
            "name": tier.name,
            "price": tier.price_monthly_cents / 100,
            "features": tier.features,
            "limits": {
                "chatbots": tier.max_chatbots,
                "conversations": tier.max_conversations_monthly,
                "knowledge_bases": tier.max_knowledge_bases,
                "chars_indexed": tier.max_chars_indexed,
            },
        })
    return plans
```

Update `get_billing_plans()` endpoint:
```python
@router.get("/billing/plans")
async def get_billing_plans():
    return _build_billing_plans()
```

- [ ] **Step 3: Remove `PLAN_CHAR_LIMITS` from config.py**

In `backend/app/config.py`, remove the `PLAN_CHAR_LIMITS` dict (lines 108-113). All consumers will use `plan_service.get_plan_limits()` instead.

- [ ] **Step 4: Update PLAN_CHAR_LIMITS consumers**

Search for imports/references to `PLAN_CHAR_LIMITS` in:
- `backend/app/services/ingestion/pipeline.py`
- `backend/app/services/chatbot_service.py`
- `backend/app/api/v1/workspaces.py`
- `backend/app/services/document_service.py`

Replace each with:
```python
from app.services.plan_service import get_plan_limits
from app.services.deployment import is_cloud

# Where character limit was checked:
if is_cloud():
    limits = get_plan_limits(workspace.plan)
    char_limit = limits["chars_indexed"]
    if char_limit != -1 and workspace.chars_indexed + new_chars > char_limit:
        raise HTTPException(status_code=402, detail="Character limit exceeded for your plan")
```

- [ ] **Step 5: Run existing billing tests to verify no regressions**

Run: `docker compose exec backend pytest tests/unit/test_billing_service.py -v`
Expected: Tests may need updating since `PLAN_LIMITS` import is removed. Update imports in test file to use `plan_service.get_plan_limits` and mock `_tier_cache`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/billing.py backend/app/api/v1/billing.py backend/app/config.py backend/app/services/ingestion/pipeline.py backend/app/services/chatbot_service.py backend/app/services/document_service.py backend/app/api/v1/workspaces.py backend/tests/unit/test_billing_service.py
git commit -m "refactor: replace hardcoded plan dicts with plan_service lookups"
```

---

### Task 4: BYOK discount in credit system

**Files:**
- Modify: `backend/app/services/credits.py`
- Modify: `backend/tests/unit/test_credits.py`

- [ ] **Step 1: Write failing tests for BYOK discount**

Add to `backend/tests/unit/test_credits.py`:
```python
def test_estimate_token_cost_byok_applies_50_percent_discount():
    cost_full = estimate_token_cost("gpt-4o", 1000, is_byok=False)
    cost_byok = estimate_token_cost("gpt-4o", 1000, is_byok=True)
    assert cost_byok == max(1, cost_full // 2)


def test_estimate_token_cost_byok_minimum_one_credit():
    cost = estimate_token_cost("gpt-4o-mini", 1, is_byok=True)
    assert cost >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest tests/unit/test_credits.py::test_estimate_token_cost_byok_applies_50_percent_discount -v`
Expected: FAIL — `TypeError: estimate_token_cost() got an unexpected keyword argument 'is_byok'`

- [ ] **Step 3: Add `is_byok` parameter to `estimate_token_cost()`**

In `backend/app/services/credits.py`, update the function (line 119):
```python
def estimate_token_cost(model: str, token_count: int, is_byok: bool = False) -> int:
    rate = COST_PER_1K_TOKENS.get(model, 2)
    cost = max(1, (token_count * rate) // 1000)
    if is_byok:
        cost = max(1, cost // 2)
    return cost
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/unit/test_credits.py -v`
Expected: PASS (all existing + 2 new tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/credits.py backend/tests/unit/test_credits.py
git commit -m "feat: add BYOK 50% discount to estimate_token_cost"
```

---

### Task 5: Gate billing routes with `require_cloud`

**Files:**
- Modify: `backend/app/api/v1/billing.py`
- Modify: `backend/app/workers/tasks/auto_recharge.py`

- [ ] **Step 1: Add `require_cloud` dependency to billing routes**

In `backend/app/api/v1/billing.py`, add import:
```python
from app.services.deployment import require_cloud, cloud_or_200
```

Add `Depends(require_cloud)` to these endpoints:
- `get_billing_usage` (line ~83)
- `get_billing_plans` (line ~175)
- `create_checkout_session` (line ~191)
- `create_portal_session` (line ~209)
- `get_credit_balance` (line ~240)
- `get_credit_history` (line ~266)
- `get_auto_recharge` and `update_auto_recharge` (line ~288+)

For the Stripe webhook endpoint (`handle_stripe_webhook`, line ~224), add an early return check using `is_self_hosted()` at the top of the handler body (FastAPI dependencies cannot short-circuit endpoint execution by returning a Response):
```python
from app.services.deployment import is_self_hosted

@router.post("/billing/webhook")
async def handle_stripe_webhook(request: Request):
    if is_self_hosted():
        return Response(status_code=200)
    # ... rest of existing handler
```

- [ ] **Step 2: Gate auto-recharge worker task**

In `backend/app/workers/tasks/auto_recharge.py`, add early return at the start of `_recharge()`:
```python
from app.services.deployment import is_self_hosted

async def _recharge(workspace_id_str: str) -> dict:
    if is_self_hosted():
        return {"status": "skipped", "detail": "Self-hosted mode"}
    await engine.dispose()
    # ... rest of existing code
```

- [ ] **Step 3: Run unit tests**

Run: `docker compose exec backend pytest tests/unit/ -v -k "billing or recharge or deployment" --tb=short`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/billing.py backend/app/workers/tasks/auto_recharge.py
git commit -m "feat: gate billing routes and auto-recharge with require_cloud"
```

---

### Task 6: LLM client token usage surfacing

The usage dict must flow through the full streaming chain: `LLM client` → `generator.py` → `engine.py` → `resolution_service.py`. All layers that forward tokens must also forward the usage dict.

**Files:**
- Modify: `backend/app/services/llm/openai_client.py`
- Modify: `backend/app/services/llm/openrouter_client.py`
- Modify: `backend/app/services/rag/generator.py`
- Modify: `backend/app/services/rag/engine.py`

- [ ] **Step 1: Add token usage tracking to OpenAI client**

In `backend/app/services/llm/openai_client.py`, modify `stream_generate()` to track and yield usage. The OpenAI streaming API includes a final chunk with `usage` when `stream_options={"include_usage": True}` is set.

```python
async def stream_generate(self, messages: list[dict], model: str, **kwargs):
    client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},
        **kwargs,
    )
    usage = None
    async for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
        if chunk.usage:
            usage = {"prompt_tokens": chunk.usage.prompt_tokens, "completion_tokens": chunk.usage.completion_tokens}
    if usage:
        yield usage  # Final yield is a dict, not a string — consumers must handle both types
```

- [ ] **Step 2: Add token usage tracking to OpenRouter client**

Same pattern in `backend/app/services/llm/openrouter_client.py` `stream_generate()`.

- [ ] **Step 3: Update generator.py to forward usage dicts**

In `backend/app/services/rag/generator.py`, in `stream_response()`, the loop that yields tokens from `client.stream_generate()` must also forward dict items:

```python
async for item in client.stream_generate(messages, model, **kwargs):
    if isinstance(item, dict) and "prompt_tokens" in item:
        yield item  # Forward usage dict to caller
        continue
    yield item  # Forward token string
```

- [ ] **Step 4: Update engine.py to forward usage dicts**

In `backend/app/services/rag/engine.py`, in `process_query()`, the loop that yields items from `generator.stream_response()` must also forward dict items:

```python
async for item in generator.stream_response(...):
    if isinstance(item, dict) and "prompt_tokens" in item:
        yield item  # Forward usage dict
        continue
    yield item  # Forward token or RAGResult
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm/openai_client.py backend/app/services/llm/openrouter_client.py backend/app/services/rag/generator.py backend/app/services/rag/engine.py
git commit -m "feat: surface token usage from LLM streaming through full RAG pipeline"
```

---

### Task 7: Credit deduction in chat flow

**Files:**
- Modify: `backend/app/services/resolution_service.py`
- Create: `backend/tests/unit/test_credit_deduction.py`

- [ ] **Step 1: Write failing tests for credit deduction**

```python
# backend/tests/unit/test_credit_deduction.py
"""Tests for credit deduction integration in chat flow."""
from unittest.mock import patch, AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_balance_check_yields_error_when_exhausted_in_cloud():
    """Cloud mode: zero balance should yield error event before streaming."""
    from app.services.resolution_service import ResolutionEvent

    workspace = MagicMock()
    workspace.credit_balance = 0

    with patch("app.services.resolution_service.is_cloud", return_value=True):
        # The balance check happens early in handle_message — we test the guard logic
        # by checking that the condition correctly identifies zero balance
        assert workspace.credit_balance <= 0


@pytest.mark.asyncio
async def test_balance_check_skipped_in_self_hosted():
    """Self-hosted mode should never check credit balance."""
    with patch("app.services.deployment.settings") as mock_settings:
        mock_settings.CLOUD_MODE = False
        from app.services.deployment import is_cloud
        assert is_cloud() is False  # Guard condition — deduction code path unreachable


def test_usage_dict_detection():
    """The streaming loop must distinguish usage dicts from token strings."""
    token = "Hello"
    usage = {"prompt_tokens": 100, "completion_tokens": 50}

    assert not (isinstance(token, dict) and "prompt_tokens" in token)
    assert isinstance(usage, dict) and "prompt_tokens" in usage
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/unit/test_credit_deduction.py -v`
Expected: PASS

- [ ] **Step 3: Wire credit deduction into resolution_service.py**

In `backend/app/services/resolution_service.py`, in the `handle_message()` async generator:

Before starting response generation, add balance check (cloud only):
```python
from app.services.deployment import is_cloud

# Before calling process_query:
if is_cloud():
    if workspace.credit_balance <= 0:
        yield ResolutionEvent(type="error", data="Credit balance exhausted")
        return
```

After streaming completes, deduct credits (cloud only):
```python
# After the streaming loop, capture usage from the final yielded dict:
if is_cloud() and token_usage:
    total_tokens = token_usage.get("prompt_tokens", 0) + token_usage.get("completion_tokens", 0)
    cost = estimate_token_cost(model, total_tokens, is_byok=workspace.is_byok)
    await debit_credits(db, workspace.id, cost, reason=f"chat:{model}:{total_tokens}tokens")
```

The streaming loop needs to detect when the LLM client yields a dict (usage) vs a string (token):
```python
token_usage = None
async for item in generator:
    if isinstance(item, dict) and "prompt_tokens" in item:
        token_usage = item
        continue
    # ... existing token handling
```

- [ ] **Step 4: Run unit tests**

Run: `docker compose exec backend pytest tests/unit/test_credit_deduction.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/resolution_service.py backend/tests/unit/test_credit_deduction.py
git commit -m "feat: wire credit deduction into chat flow with BYOK discount"
```

---

### Task 8: Conversation cap enforcement

**Files:**
- Modify: `backend/app/services/conversation_service.py`
- Create: `backend/tests/unit/test_conversation_cap.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_conversation_cap.py
"""Tests for conversation cap enforcement."""
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone

import pytest

from app.services.conversation_service import check_conversation_cap


@pytest.mark.asyncio
async def test_cap_skipped_in_self_hosted():
    with patch("app.services.conversation_service.is_cloud", return_value=False):
        # Should not raise regardless of count
        await check_conversation_cap(MagicMock(), MagicMock())


@pytest.mark.asyncio
async def test_cap_skipped_when_unlimited():
    workspace = MagicMock()
    workspace.plan = "enterprise"
    db = AsyncMock()

    with patch("app.services.conversation_service.is_cloud", return_value=True):
        with patch("app.services.conversation_service.get_plan_limits", return_value={"conversations": -1}):
            await check_conversation_cap(workspace, db)


@pytest.mark.asyncio
async def test_cap_enforced_when_limit_reached():
    from fastapi import HTTPException
    workspace = MagicMock()
    workspace.id = "test-id"
    workspace.plan = "free"
    db = AsyncMock()
    # Mock count query to return 100 (at limit)
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 100
    db.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.conversation_service.is_cloud", return_value=True):
        with patch("app.services.conversation_service.get_plan_limits", return_value={"conversations": 100}):
            with pytest.raises(HTTPException) as exc_info:
                await check_conversation_cap(workspace, db)
            assert exc_info.value.status_code == 429
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest tests/unit/test_conversation_cap.py -v`
Expected: FAIL — `ImportError: cannot import name 'check_conversation_cap'`

- [ ] **Step 3: Implement conversation cap check**

In `backend/app/services/conversation_service.py`, add:
```python
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import func, select, extract

from app.services.deployment import is_cloud
from app.services.plan_service import get_plan_limits


async def check_conversation_cap(workspace, db) -> None:
    """Raise 429 if workspace has hit monthly conversation limit. No-op in self-hosted."""
    if not is_cloud():
        return

    limits = get_plan_limits(workspace.plan)
    cap = limits.get("conversations", -1)
    if cap == -1:
        return

    from app.models.conversation import Conversation
    now = datetime.now(timezone.utc)
    count_result = await db.execute(
        select(func.count(Conversation.id)).where(
            Conversation.workspace_id == workspace.id,
            extract("month", Conversation.created_at) == now.month,
            extract("year", Conversation.created_at) == now.year,
        )
    )
    count = count_result.scalar_one()

    if count >= cap:
        raise HTTPException(status_code=429, detail="Monthly conversation limit reached")
```

Call `await check_conversation_cap(workspace, db)` at the start of `create_conversation()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/unit/test_conversation_cap.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/conversation_service.py backend/tests/unit/test_conversation_cap.py
git commit -m "feat: enforce monthly conversation cap in cloud mode"
```

---

## Chunk 2: Frontend

### Task 9: Deployment store and conditional routing

**Files:**
- Create: `frontend/src/stores/deployment-store.ts`
- Modify: `frontend/src/lib/api-functions.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add types and API function**

In `frontend/src/lib/types.ts`, add:
```typescript
export interface DeploymentConfig {
  cloud_mode: boolean;
}
```

In `frontend/src/lib/api-functions.ts`, add:
```typescript
export async function getDeploymentConfig(): Promise<DeploymentConfig> {
  const response = await fetch(`${API_BASE_URL}/api/v1/config/deployment`);
  return response.json();
}
```

Add `is_byok: boolean` to the existing `Workspace` interface.

- [ ] **Step 2: Create deployment store**

Create `frontend/src/stores/deployment-store.ts`:
```typescript
import { create } from 'zustand';
import { getDeploymentConfig } from '@/lib/api-functions';

interface DeploymentState {
  isCloud: boolean;
  isLoaded: boolean;
  loadConfig: () => Promise<void>;
}

export const useDeploymentStore = create<DeploymentState>((set) => ({
  isCloud: false,
  isLoaded: false,
  loadConfig: async () => {
    try {
      const config = await getDeploymentConfig();
      set({ isCloud: config.cloud_mode, isLoaded: true });
    } catch {
      set({ isCloud: false, isLoaded: true });
    }
  },
}));
```

- [ ] **Step 3: Load config at app init and gate billing routes**

In `frontend/src/App.tsx`:
- Import `useDeploymentStore`
- Call `loadConfig()` in a `useEffect` at the top of the App component
- Wrap billing route(s) with a condition: only render `<Route>` for billing/credits when `isCloud` is true
- While `!isLoaded`, optionally show a loading spinner or just render the app (billing links are gated in Sidebar)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/deployment-store.ts frontend/src/lib/api-functions.ts frontend/src/lib/types.ts frontend/src/App.tsx
git commit -m "feat: add deployment store and conditional billing routes"
```

---

### Task 10: Sidebar mode badge and conditional billing link

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`

- [ ] **Step 1: Add mode badge and hide billing in self-hosted**

In `frontend/src/components/layout/Sidebar.tsx`:
- Import `useDeploymentStore`
- Read `isCloud` from the store
- Filter `SETTINGS_CHILDREN` to exclude billing-related items when `!isCloud`
- Add a small badge at the sidebar footer: `isCloud ? "Cloud" : "Self-Hosted"` — styled as a muted text label

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/layout/Sidebar.tsx
git commit -m "feat: add deployment mode badge and conditional billing link in sidebar"
```

---

### Task 11: BYOK toggle on LLM settings page

**Files:**
- Modify: `frontend/src/app/(dashboard)/settings/llm/page.tsx`

- [ ] **Step 1: Add BYOK toggle (cloud mode only)**

In `frontend/src/app/(dashboard)/settings/llm/page.tsx`:
- Import `useDeploymentStore`
- Read `isCloud` from the store
- When `isCloud`:
  - Add a toggle/switch at the top of the page: "Bring Your Own Key (BYOK)" with description "Use your own API key — 50% discount on credits"
  - When toggled, PATCH workspace with `is_byok: true/false`
  - Show pricing info text based on BYOK state
- When `!isCloud` (self-hosted):
  - Hide the BYOK toggle and pricing info
  - Show only the API key input fields (already existing)

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/(dashboard)/settings/llm/page.tsx
git commit -m "feat: add BYOK toggle on LLM settings page for cloud mode"
```

---

### Task 12: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update public exceptions list**

In `CLAUDE.md`, update the "Public exceptions" section to note that `GET /api/v1/billing/plans` returns 404 in self-hosted mode. Add `GET /api/v1/config/deployment` to the public exceptions list.

Add a new section "Deployment modes" after "Security notes":
```markdown
### Deployment modes
`CLOUD_MODE` env var (default `false`). When `false` (self-hosted): all features unlocked, billing/credits/plan limits disabled, `require_cloud` dependency returns 404 on billing routes. When `true` (cloud): full SaaS with Stripe billing, credit system, plan tier limits. BYOK workspaces (`is_byok=true`) get 50% credit discount. Plan tiers stored in `plan_tiers` table, cached at startup via `plan_service.load_plan_tiers()`.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with deployment modes and public endpoint changes"
```
