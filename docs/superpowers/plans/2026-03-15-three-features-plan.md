# Multi-language, Webhook Retry, Worker Health Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add auto-detect language toggle, webhook delivery retries with dead letter queue, and worker health dashboard.

**Architecture:** Three independent features sharing no code. Feature 1 is prompt-only (model + schema + template change). Feature 2 adds a new model, Celery task, and API endpoints. Feature 3 adds an aggregation endpoint and frontend tab.

**Tech Stack:** FastAPI, SQLAlchemy async, Celery, PostgreSQL, React + Recharts, Vitest

**Spec:** `docs/superpowers/specs/2026-03-15-three-features-design.md`

---

## Chunk 1: Multi-language Auto-detection

### File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `backend/app/models/knowledge.py` | Add `auto_detect_language` column to `Chatbot` |
| Create | `backend/alembic/versions/2026_03_15_chatbot_auto_detect_language.py` | Migration |
| Modify | `backend/app/schemas/widget.py` | Add field to `PersonaUpdate` |
| Modify | `backend/app/schemas/chatbots.py` | Add field to `ChatbotUpdate` and `ChatbotResponse` |
| Modify | `backend/app/services/rag/prompts.py` | Conditional language instruction |
| Create | `backend/tests/unit/test_language_prompt.py` | Test prompt generation |
| Modify | `frontend/src/lib/types.ts` | Add `auto_detect_language` to `Chatbot` |
| Modify | `frontend/src/app/(dashboard)/chatbots/[id]/setup/page.tsx` | Toggle UI |

---

### Task 1: Add `auto_detect_language` column to Chatbot model

**Files:**
- Modify: `backend/app/models/knowledge.py:22` (after `language` column)

- [ ] **Step 1: Add column to model**

In `backend/app/models/knowledge.py`, add after line 22 (`language` column):

```python
auto_detect_language: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
```

- [ ] **Step 2: Create migration**

Run:
```bash
docker compose exec backend alembic revision --autogenerate -m "chatbot auto_detect_language"
```

Rename the generated file to `2026_03_15_chatbot_auto_detect_language.py`.

- [ ] **Step 3: Run migration**

```bash
docker compose exec backend alembic upgrade head
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/knowledge.py backend/alembic/versions/2026_03_15_chatbot_auto_detect_language.py
git commit -m "feat: add auto_detect_language column to chatbots"
```

---

### Task 2: Update schemas

**Files:**
- Modify: `backend/app/schemas/widget.py:101-107` (`PersonaUpdate` class)
- Modify: `backend/app/schemas/chatbots.py:35-66` (`ChatbotUpdate`) and `82-113` (`ChatbotResponse`)

- [ ] **Step 1: Add to PersonaUpdate**

In `backend/app/schemas/widget.py`, add after line 106 (`language: str | None = None`):

```python
auto_detect_language: bool | None = None
```

- [ ] **Step 2: Add to ChatbotUpdate**

In `backend/app/schemas/chatbots.py`, add after `use_hybrid_retrieval: bool | None = None` (line 58):

```python
auto_detect_language: bool | None = None
```

- [ ] **Step 3: Add to ChatbotResponse**

In `backend/app/schemas/chatbots.py`, add after `use_hybrid_retrieval: bool` (line 99):

```python
auto_detect_language: bool = False
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/widget.py backend/app/schemas/chatbots.py
git commit -m "feat: add auto_detect_language to persona/chatbot schemas"
```

---

### Task 3: Conditional language instruction in system prompt (TDD)

**Files:**
- Create: `backend/tests/unit/test_language_prompt.py`
- Modify: `backend/app/services/rag/prompts.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/test_language_prompt.py`:

```python
"""Tests for language instruction in system prompt."""
from unittest.mock import MagicMock

from app.services.rag.prompts import build_system_prompt


def _make_chatbot(auto_detect: bool = False, language: str = "en") -> MagicMock:
    bot = MagicMock()
    bot.display_name = "TestBot"
    bot.name = "Test Chatbot"
    bot.tone = "friendly"
    bot.language = language
    bot.system_prompt = ""
    bot.auto_detect_language = auto_detect
    return bot


def test_default_language_instruction():
    """When auto_detect_language is False, prompt says 'You respond in {language}'."""
    bot = _make_chatbot(auto_detect=False, language="French")
    prompt = build_system_prompt(bot)
    assert "You respond in French" in prompt
    assert "Detect the language" not in prompt


def test_auto_detect_language_instruction():
    """When auto_detect_language is True, prompt includes detection instruction."""
    bot = _make_chatbot(auto_detect=True, language="English")
    prompt = build_system_prompt(bot)
    assert "Detect the language" in prompt
    assert "default to English" in prompt
    assert "You respond in English." not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend pytest tests/unit/test_language_prompt.py -v
```

Expected: `test_auto_detect_language_instruction` FAILS (prompt still says "You respond in {language}").

- [ ] **Step 3: Implement conditional language instruction**

Replace the contents of `backend/app/services/rag/prompts.py`:

```python
from app.models.knowledge import Chatbot, Chunk

CITATION_INSTRUCTION = """When answering, cite your sources using numbered references like [1], [2], etc.
Only use information from the provided context. If the context doesn't contain enough information to answer the question confidently, say so clearly rather than guessing."""

PERSONA_TEMPLATE = """You are {display_name}, an AI assistant for {chatbot_name}.
Your tone is {tone}. {language_instruction}

{system_prompt}

{citation_instruction}"""


def _build_language_instruction(chatbot: Chatbot) -> str:
    language = chatbot.language or "English"
    if getattr(chatbot, "auto_detect_language", False):
        return (
            "Detect the language of the user's message and always respond in that same language. "
            f"If unsure, default to {language}."
        )
    return f"You respond in {language}."


def build_system_prompt(chatbot: Chatbot) -> str:
    return PERSONA_TEMPLATE.format(
        display_name=chatbot.display_name or "Assistant",
        chatbot_name=chatbot.name,
        tone=chatbot.tone or "professional",
        language_instruction=_build_language_instruction(chatbot),
        system_prompt=chatbot.system_prompt or "",
        citation_instruction=CITATION_INSTRUCTION,
    ).strip()


def build_context_prompt(chunks: list[tuple[Chunk, float]]) -> str:
    if not chunks:
        return "No relevant context found."

    parts = ["Here is the relevant context:\n"]
    for i, (chunk, score) in enumerate(chunks, 1):
        heading = f" ({chunk.heading_path})" if chunk.heading_path else ""
        parts.append(f"[{i}]{heading}:\n{chunk.content}\n")

    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose exec backend pytest tests/unit/test_language_prompt.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/rag/prompts.py backend/tests/unit/test_language_prompt.py
git commit -m "feat: conditional language detection in system prompt"
```

---

### Task 4: Frontend toggle

**Files:**
- Modify: `frontend/src/lib/types.ts` (add `auto_detect_language` to `Chatbot` interface)
- Modify: `frontend/src/app/(dashboard)/chatbots/[id]/setup/page.tsx` (toggle in persona review step)

- [ ] **Step 1: Add type**

In `frontend/src/lib/types.ts`, find the `Chatbot` interface and add after `use_hybrid_retrieval`:

```typescript
auto_detect_language: boolean;
```

- [ ] **Step 2: Add toggle to setup page**

In `frontend/src/app/(dashboard)/chatbots/[id]/setup/page.tsx`, find the language selector in the persona review step. Add a toggle checkbox below it:

```tsx
<label className="flex items-center gap-2 mt-2">
  <input
    type="checkbox"
    checked={reviewAutoDetect}
    onChange={(e) => setReviewAutoDetect(e.target.checked)}
    className="rounded border-gray-300"
  />
  <span className="text-sm text-gray-600">
    Auto-detect visitor language
  </span>
</label>
```

Add the state variable alongside existing review state:
```tsx
const [reviewAutoDetect, setReviewAutoDetect] = useState(false);
```

Initialize it from the chatbot data (alongside `setReviewLanguage`):
```tsx
setReviewAutoDetect(bot.auto_detect_language ?? false);
```

Include it in the save payload for the persona update API call:
```tsx
auto_detect_language: reviewAutoDetect,
```

Relabel the language dropdown when auto-detect is enabled — change the label from "Language" to "Fallback language" conditionally.

- [ ] **Step 3: Test manually**

1. Open http://localhost:3001, navigate to a chatbot's setup page.
2. Toggle "Auto-detect visitor language" on.
3. Verify the language dropdown label changes to "Fallback language".
4. Save and verify the API call includes `auto_detect_language: true`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/app/\(dashboard\)/chatbots/\[id\]/setup/page.tsx
git commit -m "feat: add auto-detect language toggle to setup page"
```

---

## Chunk 2: Webhook Retry with Dead Letter Queue

### File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `backend/app/models/webhook_delivery.py` | WebhookDelivery model |
| Create | `backend/alembic/versions/2026_03_15_webhook_deliveries.py` | Migration |
| Modify | `backend/app/models/__init__.py` | Register new model |
| Create | `backend/app/schemas/webhook_delivery.py` | Response schemas |
| Modify | `backend/app/services/webhooks.py` | Refactor fire_event as orchestrator |
| Create | `backend/app/workers/tasks/deliver_webhook.py` | Celery retry task |
| Modify | `backend/app/workers/celery_app.py` | Register new task |
| Modify | `backend/app/api/v1/webhooks.py` | Add delivery list + retry endpoints |
| Create | `backend/tests/unit/test_webhook_delivery.py` | Tests |
| Modify | `frontend/src/lib/types.ts` | WebhookDelivery type |
| Modify | `frontend/src/lib/api-functions.ts` | API functions |
| Modify | `frontend/src/app/(dashboard)/settings/webhooks/page.tsx` | Delivery UI |

---

### Task 5: WebhookDelivery model

**Files:**
- Create: `backend/app/models/webhook_delivery.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create model file**

Create `backend/app/models/webhook_delivery.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampUpdateMixin, UUIDPrimaryKeyMixin


class WebhookDelivery(UUIDPrimaryKeyMixin, TimestampUpdateMixin, Base):
    __tablename__ = "webhook_deliveries"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    webhook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspace_webhooks.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_webhook_deliveries_webhook_status", "webhook_id", "status"),
        Index("ix_webhook_deliveries_status_retry", "status", "next_retry_at"),
        Index("ix_webhook_deliveries_webhook_created", "webhook_id", "created_at"),
    )
```

- [ ] **Step 2: Register in models __init__**

In `backend/app/models/__init__.py`, add import and __all__ entry:

```python
from app.models.webhook_delivery import WebhookDelivery  # noqa: F401
```

Add `"WebhookDelivery"` to the `__all__` list.

- [ ] **Step 3: Create migration**

```bash
docker compose exec backend alembic revision --autogenerate -m "webhook_deliveries"
```

Rename to `2026_03_15_webhook_deliveries.py`.

- [ ] **Step 4: Run migration**

```bash
docker compose exec backend alembic upgrade head
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/webhook_delivery.py backend/app/models/__init__.py backend/alembic/versions/2026_03_15_webhook_deliveries.py
git commit -m "feat: add WebhookDelivery model with retry indexes"
```

---

### Task 6: Webhook delivery schemas

**Files:**
- Create: `backend/app/schemas/webhook_delivery.py`

- [ ] **Step 1: Create schema file**

Create `backend/app/schemas/webhook_delivery.py`:

```python
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WebhookDeliveryResponse(BaseModel):
    id: uuid.UUID
    webhook_id: uuid.UUID
    event_type: str
    status: str
    attempts: int
    max_attempts: int
    next_retry_at: Optional[datetime] = None
    last_status_code: Optional[int] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryListResponse(BaseModel):
    items: list[WebhookDeliveryResponse]
    total: int
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/webhook_delivery.py
git commit -m "feat: add webhook delivery response schemas"
```

---

### Task 7: Refactor fire_event + deliver_webhook task (TDD)

**Files:**
- Create: `backend/tests/unit/test_webhook_delivery.py`
- Modify: `backend/app/services/webhooks.py`
- Create: `backend/app/workers/tasks/deliver_webhook.py`
- Modify: `backend/app/workers/celery_app.py`

- [ ] **Step 1: Write tests for fire_event orchestration**

Create `backend/tests/unit/test_webhook_delivery.py`:

```python
"""Tests for webhook delivery orchestration and retry logic."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.webhook_delivery import WebhookDelivery


@pytest.mark.asyncio
async def test_fire_event_creates_delivery_rows(db):
    """fire_event should create WebhookDelivery rows and dispatch tasks."""
    from app.models.organizational import WorkspaceWebhook
    from app.services.webhooks import fire_event

    workspace_id = uuid.uuid4()

    # Create a webhook in the test DB
    hook = WorkspaceWebhook(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        url="https://example.com/hook",
        event_types=["conversation.created"],
        is_active=True,
    )
    db.add(hook)
    await db.flush()

    mock_task = MagicMock()
    mock_task.delay = MagicMock()
    with patch("app.services.webhooks._get_deliver_task", return_value=mock_task):
        await fire_event(workspace_id, "conversation.created", {"foo": "bar"}, db_session=db)

    # Check delivery row was created
    from sqlalchemy import select
    result = await db.execute(
        select(WebhookDelivery).where(WebhookDelivery.webhook_id == hook.id)
    )
    delivery = result.scalar_one()
    assert delivery.status == "pending"
    assert delivery.event_type == "conversation.created"
    assert delivery.workspace_id == workspace_id
    mock_task.delay.assert_called_once_with(str(delivery.id))


@pytest.mark.asyncio
async def test_fire_event_skips_non_matching_events(db):
    """fire_event should not create deliveries for non-matching event types."""
    from app.models.organizational import WorkspaceWebhook
    from app.services.webhooks import fire_event

    workspace_id = uuid.uuid4()
    hook = WorkspaceWebhook(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        url="https://example.com/hook",
        event_types=["conversation.resolved"],
        is_active=True,
    )
    db.add(hook)
    await db.flush()

    mock_task = MagicMock()
    mock_task.delay = MagicMock()
    with patch("app.services.webhooks._get_deliver_task", return_value=mock_task):
        await fire_event(workspace_id, "conversation.created", {"foo": "bar"}, db_session=db)

    mock_task.delay.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend pytest tests/unit/test_webhook_delivery.py -v
```

Expected: FAIL (fire_event doesn't accept `db_session` param yet, doesn't create delivery rows).

- [ ] **Step 3: Refactor fire_event**

Replace `backend/app/services/webhooks.py`:

```python
"""Outbound webhook delivery service."""

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.organizational import WorkspaceWebhook
from app.models.webhook_delivery import WebhookDelivery
from app.services.encryption import decrypt_api_key

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency — set after celery_app is loaded
deliver_webhook_task = None


def _get_deliver_task():
    global deliver_webhook_task
    if deliver_webhook_task is None:
        from app.workers.tasks.deliver_webhook import deliver_webhook
        deliver_webhook_task = deliver_webhook
    return deliver_webhook_task


async def fire_event(
    workspace_id: uuid.UUID,
    event_type: str,
    payload: dict,
    db_session: AsyncSession | None = None,
) -> None:
    """Create WebhookDelivery rows for matching webhooks and dispatch Celery tasks."""

    _pending_delivery_ids: list[uuid.UUID] = []

    async def _inner(session: AsyncSession) -> None:
        result = await session.execute(
            select(WorkspaceWebhook).where(
                WorkspaceWebhook.workspace_id == workspace_id,
                WorkspaceWebhook.is_active == True,  # noqa: E712
            )
        )
        hooks = result.scalars().all()

        for hook in hooks:
            if event_type not in (hook.event_types or []):
                continue
            delivery = WebhookDelivery(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                webhook_id=hook.id,
                event_type=event_type,
                payload={
                    "event": event_type,
                    "workspace_id": str(workspace_id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": payload,
                },
                status="pending",
            )
            session.add(delivery)
            await session.flush()
            _pending_delivery_ids.append(delivery.id)

    if db_session is not None:
        await _inner(db_session)
    else:
        async with async_session_factory() as session:
            await _inner(session)
            await session.commit()

    # Dispatch tasks AFTER commit — workers read from DB (see CLAUDE.md crawl pipeline note).
    task = _get_deliver_task()
    for did in _pending_delivery_ids:
        task.delay(str(did))


def build_signature(secret: str, body: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload."""
    return f"sha256={hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()}"
```

- [ ] **Step 4: Create deliver_webhook Celery task**

Create `backend/app/workers/tasks/deliver_webhook.py`:

```python
"""Celery task for delivering individual webhook with retries."""

import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy import select

from app.database import async_session_factory, engine
from app.models.organizational import WorkspaceWebhook
from app.models.webhook_delivery import WebhookDelivery
from app.services.encryption import decrypt_api_key
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

RETRY_DELAYS = [60, 300, 900, 3600, 10800]  # ~4.2 hours total


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def deliver_webhook(self, delivery_id: str) -> dict:
    try:
        return asyncio.run(_deliver(uuid.UUID(delivery_id), self))
    except Exception as exc:
        # Celery retry is handled inside _deliver; re-raise only unexpected errors
        raise


async def _deliver(delivery_id: uuid.UUID, task) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        # Load delivery + webhook
        result = await session.execute(
            select(WebhookDelivery).where(WebhookDelivery.id == delivery_id)
        )
        delivery = result.scalar_one_or_none()
        if delivery is None:
            logger.error(f"WebhookDelivery {delivery_id} not found")
            return {"status": "error", "detail": "Delivery not found"}

        hook_result = await session.execute(
            select(WorkspaceWebhook).where(WorkspaceWebhook.id == delivery.webhook_id)
        )
        hook = hook_result.scalar_one_or_none()
        if hook is None:
            delivery.status = "failed"
            delivery.last_error = "Webhook deleted"
            await session.commit()
            return {"status": "failed", "detail": "Webhook deleted"}

        # Build request
        body = json.dumps(delivery.payload)
        headers = {"Content-Type": "application/json"}
        if hook.secret:
            try:
                secret = decrypt_api_key(hook.secret)
            except Exception:
                secret = hook.secret
            sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers["X-Pulse-Signature"] = f"sha256={sig}"

        # Attempt delivery
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(hook.url, content=body, headers=headers)
            delivery.last_status_code = resp.status_code

            if 200 <= resp.status_code < 300:
                delivery.status = "delivered"
                delivery.attempts += 1
                await session.commit()
                return {"status": "delivered", "status_code": resp.status_code}
            else:
                error_msg = f"HTTP {resp.status_code}"
                delivery.last_error = error_msg

        except Exception as exc:
            delivery.last_error = str(exc)[:500]

        # Failed — increment attempts and decide retry vs dead letter
        delivery.attempts += 1

        if delivery.attempts >= delivery.max_attempts:
            delivery.status = "failed"
            delivery.next_retry_at = None
            await session.commit()
            logger.warning(f"Webhook delivery {delivery_id} exhausted retries")
            return {"status": "failed", "attempts": delivery.attempts}

        # Schedule retry
        delay_idx = min(delivery.attempts - 1, len(RETRY_DELAYS) - 1)
        delay = RETRY_DELAYS[delay_idx]
        delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        await session.commit()

        raise task.retry(countdown=delay)
```

- [ ] **Step 5: Register task in celery_app**

In `backend/app/workers/celery_app.py`, add to `conf.include` list:

```python
"app.workers.tasks.deliver_webhook",
```

- [ ] **Step 6: Run tests**

```bash
docker compose exec backend pytest tests/unit/test_webhook_delivery.py -v
```

Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/webhooks.py backend/app/workers/tasks/deliver_webhook.py backend/app/workers/celery_app.py backend/tests/unit/test_webhook_delivery.py
git commit -m "feat: webhook retry with dead letter queue"
```

---

### Task 8: Webhook delivery API endpoints

**Files:**
- Modify: `backend/app/api/v1/webhooks.py`

- [ ] **Step 1: Add delivery list and retry endpoints**

Add to the bottom of `backend/app/api/v1/webhooks.py`:

```python
from app.models.webhook_delivery import WebhookDelivery
from app.schemas.webhook_delivery import WebhookDeliveryListResponse, WebhookDeliveryResponse


@router.get(
    "/workspaces/{workspace_id}/webhooks/{webhook_id}/deliveries",
    response_model=WebhookDeliveryListResponse,
)
async def list_deliveries(
    webhook_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace_admin),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List delivery attempts for a webhook, newest first."""
    # Verify webhook belongs to workspace
    hook_result = await db.execute(
        select(WorkspaceWebhook).where(
            WorkspaceWebhook.id == webhook_id,
            WorkspaceWebhook.workspace_id == workspace_id,
        )
    )
    if hook_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    from sqlalchemy import func

    base_filters = [
        WebhookDelivery.webhook_id == webhook_id,
        WebhookDelivery.workspace_id == workspace_id,
    ]
    if status_filter:
        base_filters.append(WebhookDelivery.status == status_filter)

    total_result = await db.execute(
        select(func.count(WebhookDelivery.id)).where(*base_filters)
    )
    total = total_result.scalar_one()

    query = select(WebhookDelivery).where(*base_filters)

    result = await db.execute(
        query.order_by(WebhookDelivery.created_at.desc()).limit(limit).offset(offset)
    )
    deliveries = result.scalars().all()

    return WebhookDeliveryListResponse(items=deliveries, total=total)


@router.post(
    "/workspaces/{workspace_id}/webhooks/{webhook_id}/deliveries/{delivery_id}/retry",
    response_model=WebhookDeliveryResponse,
)
async def retry_delivery(
    webhook_id: uuid.UUID,
    delivery_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace_admin),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    """Retry a failed webhook delivery."""
    result = await db.execute(
        select(WebhookDelivery).where(
            WebhookDelivery.id == delivery_id,
            WebhookDelivery.webhook_id == webhook_id,
            WebhookDelivery.workspace_id == workspace_id,
        )
    )
    delivery = result.scalar_one_or_none()
    if delivery is None or delivery.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failed delivery not found",
        )

    delivery.status = "pending"
    delivery.attempts = 0
    delivery.next_retry_at = None
    delivery.last_error = None
    await db.commit()
    await db.refresh(delivery)

    from app.workers.tasks.deliver_webhook import deliver_webhook
    deliver_webhook.delay(str(delivery_id))

    return delivery
```

- [ ] **Step 2: Restart backend and verify endpoints**

```bash
docker compose restart backend
```

Check the new endpoints appear at http://localhost:8000/api/docs.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/webhooks.py
git commit -m "feat: add webhook delivery list and retry endpoints"
```

---

### Task 9: Frontend webhook deliveries UI

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api-functions.ts`
- Modify: `frontend/src/app/(dashboard)/settings/webhooks/page.tsx`

- [ ] **Step 1: Add types**

In `frontend/src/lib/types.ts`, add after the `Webhook` interface:

```typescript
export interface WebhookDelivery {
  id: string;
  webhook_id: string;
  event_type: string;
  status: "pending" | "delivered" | "failed";
  attempts: number;
  max_attempts: number;
  next_retry_at: string | null;
  last_status_code: number | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: Add API functions**

In `frontend/src/lib/api-functions.ts`, add after `deleteWebhook`:

```typescript
import { WebhookDelivery } from "./types";

export function getWebhookDeliveries(
  workspaceId: string,
  webhookId: string,
  params?: { status?: string; limit?: number; offset?: number },
) {
  const query = new URLSearchParams();
  if (params?.status) query.set("status_filter", params.status);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qs = query.toString();
  return api.get<{ items: WebhookDelivery[]; total: number }>(
    `/api/v1/workspaces/${workspaceId}/webhooks/${webhookId}/deliveries${qs ? `?${qs}` : ""}`,
  );
}

export function retryWebhookDelivery(
  workspaceId: string,
  webhookId: string,
  deliveryId: string,
) {
  return api.post<WebhookDelivery>(
    `/api/v1/workspaces/${workspaceId}/webhooks/${webhookId}/deliveries/${deliveryId}/retry`,
    {},
  );
}
```

- [ ] **Step 3: Add expandable delivery rows to webhooks page**

In `frontend/src/app/(dashboard)/settings/webhooks/page.tsx`, update the webhook list to make each row expandable. When expanded, fetch and show recent deliveries with status badges and a retry button for failed ones.

Key UI elements:
- Chevron toggle on each webhook row to expand/collapse.
- When expanded: call `getWebhookDeliveries(workspaceId, webhookId, { limit: 10 })`.
- Show delivery rows: event type, status badge (green/red/yellow), attempts, timestamp.
- "Retry" button on failed deliveries calls `retryWebhookDelivery(...)`.

- [ ] **Step 4: Test manually**

1. Create a webhook pointing to a test URL (e.g., https://httpbin.org/status/500 to force failures).
2. Trigger an event (create a conversation, etc.).
3. Expand the webhook row and verify delivery appears.
4. For failed deliveries, click Retry and verify it resets.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api-functions.ts frontend/src/app/\(dashboard\)/settings/webhooks/page.tsx
git commit -m "feat: webhook delivery UI with retry button"
```

---

## Chunk 3: Worker Health Dashboard

### File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `backend/app/models/task_log.py` | Add `retry_count` column |
| Create | `backend/alembic/versions/2026_03_15_task_log_retry_count.py` | Migration |
| Create | `backend/app/schemas/worker_health.py` | Response schemas |
| Modify | `backend/app/api/v1/logs.py` | Add worker health endpoint |
| Create | `backend/tests/unit/test_worker_health.py` | Tests |
| Modify | `frontend/src/lib/types.ts` | WorkerHealth types |
| Modify | `frontend/src/lib/api-functions.ts` | API function |
| Modify | `frontend/src/app/(dashboard)/logs/page.tsx` | Workers tab |

---

### Task 10: Add retry_count to BackgroundTaskLog

**Files:**
- Modify: `backend/app/models/task_log.py`

- [ ] **Step 1: Add column**

In `backend/app/models/task_log.py`, add after `duration_ms` (line 21):

```python
retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
```

- [ ] **Step 2: Create and run migration**

```bash
docker compose exec backend alembic revision --autogenerate -m "task_log_retry_count"
docker compose exec backend alembic upgrade head
```

Rename to `2026_03_15_task_log_retry_count.py`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/task_log.py backend/alembic/versions/2026_03_15_task_log_retry_count.py
git commit -m "feat: add retry_count to background_task_logs"
```

---

### Task 11: Worker health response schemas

**Files:**
- Create: `backend/app/schemas/worker_health.py`

- [ ] **Step 1: Create schema file**

Create `backend/app/schemas/worker_health.py`:

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class QueueStats(BaseModel):
    pending: int
    running: int
    throughput_per_hour: float


class TopError(BaseModel):
    task_name: str
    error: str
    count: int


class ReliabilityStats(BaseModel):
    total: int
    succeeded: int
    failed: int
    failure_rate_pct: float
    total_retries: int
    top_errors: list[TopError]


class TaskPerformance(BaseModel):
    task_name: str
    count: int
    success_rate_pct: float
    avg_duration_ms: Optional[float] = None
    p95_duration_ms: Optional[float] = None
    last_failure_at: Optional[datetime] = None


class PerformanceStats(BaseModel):
    by_task: list[TaskPerformance]


class TimeseriesBucket(BaseModel):
    bucket: datetime
    completed: int
    failed: int


class WorkerHealthResponse(BaseModel):
    queue: QueueStats
    reliability: ReliabilityStats
    performance: PerformanceStats
    timeseries: list[TimeseriesBucket]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/worker_health.py
git commit -m "feat: add worker health response schemas"
```

---

### Task 12: Worker health API endpoint (TDD)

**Files:**
- Create: `backend/tests/unit/test_worker_health.py`
- Modify: `backend/app/api/v1/logs.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_worker_health.py`:

```python
"""Tests for worker health endpoint."""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio

from app.models.task_log import BackgroundTaskLog


@pytest.mark.asyncio
async def test_worker_health_empty(auth_client, workspace):
    """Returns zero stats when no task logs exist."""
    resp = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/workers/health?window=24h"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["queue"]["pending"] == 0
    assert data["queue"]["running"] == 0
    assert data["reliability"]["total"] == 0
    assert data["reliability"]["failure_rate_pct"] == 0.0
    assert data["performance"]["by_task"] == []
    assert data["timeseries"] == []


@pytest.mark.asyncio
async def test_worker_health_with_data(auth_client, workspace, db):
    """Returns correct aggregated stats."""
    now = datetime.now(timezone.utc)

    # Create some task logs
    for i in range(5):
        log = BackgroundTaskLog(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            task_name="ingest_document",
            task_id=f"task-{i}",
            status="completed",
            started_at=now - timedelta(hours=1),
            completed_at=now - timedelta(minutes=30),
            duration_ms=3000 + (i * 100),
        )
        db.add(log)

    # Add a failed task
    failed = BackgroundTaskLog(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        task_name="crawl_website",
        task_id="task-fail",
        status="failed",
        started_at=now - timedelta(hours=1),
        completed_at=now - timedelta(minutes=50),
        duration_ms=500,
        error="Connection timeout",
    )
    db.add(failed)

    # Add a running task (should appear in queue)
    running = BackgroundTaskLog(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        task_name="analyze_conversation",
        task_id="task-running",
        status="running",
        started_at=now - timedelta(minutes=2),
    )
    db.add(running)
    await db.flush()

    resp = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/workers/health?window=24h"
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["queue"]["running"] == 1
    # total = completed (5) + failed (1) = 6; running task excluded from reliability
    assert data["reliability"]["total"] == 6
    assert data["reliability"]["succeeded"] == 5
    assert data["reliability"]["failed"] == 1
    assert len(data["performance"]["by_task"]) >= 2

    # Check ingest_document performance
    ingest = next(t for t in data["performance"]["by_task"] if t["task_name"] == "ingest_document")
    assert ingest["count"] == 5
    assert ingest["success_rate_pct"] == 100.0
    assert ingest["avg_duration_ms"] is not None


@pytest.mark.asyncio
async def test_worker_health_requires_admin(auth_client, workspace):
    """Non-admin access should be forbidden (get_workspace_admin dependency)."""
    # The auth_client fixture uses an admin user, so this test validates the endpoint exists.
    # Tenant isolation / admin enforcement is tested in test_admin_role_enforcement.py.
    resp = await auth_client.get(
        f"/api/v1/workspaces/{workspace.id}/workers/health"
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend pytest tests/unit/test_worker_health.py -v
```

Expected: FAIL (404 — endpoint doesn't exist yet).

- [ ] **Step 3: Implement the endpoint**

Add to `backend/app/api/v1/logs.py`. First, add imports at the top:

```python
from datetime import datetime, timezone, timedelta
from typing import Literal

from app.dependencies import get_workspace_admin
from app.models.task_log import BackgroundTaskLog
from app.schemas.worker_health import (
    WorkerHealthResponse,
    QueueStats,
    ReliabilityStats,
    PerformanceStats,
    TaskPerformance,
    TimeseriesBucket,
    TopError,
)
```

Then add the endpoint:

```python
@router.get("/workers/health", response_model=WorkerHealthResponse)
async def get_worker_health(
    workspace_id: uuid.UUID = Depends(get_workspace_admin),
    db: AsyncSession = Depends(get_db),
    window: Literal["1h", "24h", "7d"] = "24h",
) -> WorkerHealthResponse:
    """Aggregated worker health metrics for the workspace."""
    window_map = {"1h": timedelta(hours=1), "24h": timedelta(hours=24), "7d": timedelta(days=7)}
    cutoff = datetime.now(timezone.utc) - window_map[window]

    # Queue stats (live — no time window filter)
    queue_result = await db.execute(
        select(
            BackgroundTaskLog.status,
            func.count(BackgroundTaskLog.id),
        )
        .where(
            BackgroundTaskLog.workspace_id == workspace_id,
            BackgroundTaskLog.status.in_(["pending", "running"]),
        )
        .group_by(BackgroundTaskLog.status)
    )
    queue_counts = dict(queue_result.all())
    pending = queue_counts.get("pending", 0)
    running = queue_counts.get("running", 0)

    # All tasks in window
    window_filter = [
        BackgroundTaskLog.workspace_id == workspace_id,
        BackgroundTaskLog.started_at >= cutoff,
    ]

    # Reliability — only count completed + failed tasks (exclude running/pending)
    rel_result = await db.execute(
        select(
            func.count(BackgroundTaskLog.id),
            func.count(BackgroundTaskLog.id).filter(BackgroundTaskLog.status == "completed"),
            func.count(BackgroundTaskLog.id).filter(BackgroundTaskLog.status == "failed"),
            func.coalesce(func.sum(BackgroundTaskLog.retry_count), 0),
        ).where(
            *window_filter,
            BackgroundTaskLog.status.in_(["completed", "failed"]),
        )
    )
    total, succeeded, failed, total_retries = rel_result.one()
    failure_rate = round((failed / total * 100) if total > 0 else 0.0, 2)

    # Throughput
    hours = window_map[window].total_seconds() / 3600
    throughput = round(succeeded / hours, 1) if hours > 0 else 0.0

    # Top errors
    from sqlalchemy import desc
    errors_result = await db.execute(
        select(
            BackgroundTaskLog.task_name,
            BackgroundTaskLog.error,
            func.count(BackgroundTaskLog.id).label("cnt"),
        )
        .where(
            *window_filter,
            BackgroundTaskLog.status == "failed",
            BackgroundTaskLog.error.isnot(None),
        )
        .group_by(BackgroundTaskLog.task_name, BackgroundTaskLog.error)
        .order_by(desc("cnt"))
        .limit(10)
    )
    top_errors = [TopError(task_name=r[0], error=r[1], count=r[2]) for r in errors_result.all()]

    # Performance by task
    from sqlalchemy import case, literal_column
    perf_result = await db.execute(
        select(
            BackgroundTaskLog.task_name,
            func.count(BackgroundTaskLog.id).label("count"),
            (
                func.count(BackgroundTaskLog.id).filter(BackgroundTaskLog.status == "completed")
                * 100.0
                / func.nullif(func.count(BackgroundTaskLog.id), 0)
            ).label("success_rate"),
            func.avg(BackgroundTaskLog.duration_ms).filter(
                BackgroundTaskLog.duration_ms.isnot(None)
            ).label("avg_ms"),
            func.percentile_cont(0.95).within_group(
                BackgroundTaskLog.duration_ms
            ).filter(
                BackgroundTaskLog.duration_ms.isnot(None)
            ).label("p95_ms"),
            func.max(BackgroundTaskLog.started_at).filter(
                BackgroundTaskLog.status == "failed"
            ).label("last_fail"),
        )
        .where(*window_filter)
        .group_by(BackgroundTaskLog.task_name)
        .order_by(desc("count"))
    )
    by_task = [
        TaskPerformance(
            task_name=r.task_name,
            count=r.count,
            success_rate_pct=round(float(r.success_rate or 0), 1),
            avg_duration_ms=round(float(r.avg_ms)) if r.avg_ms else None,
            p95_duration_ms=round(float(r.p95_ms)) if r.p95_ms else None,
            last_failure_at=r.last_fail,
        )
        for r in perf_result.all()
    ]

    # Timeseries
    if window == "7d":
        bucket_expr = func.date_trunc("day", BackgroundTaskLog.started_at)
    else:
        bucket_expr = func.date_trunc("hour", BackgroundTaskLog.started_at)

    ts_result = await db.execute(
        select(
            bucket_expr.label("bucket"),
            func.count(BackgroundTaskLog.id).filter(
                BackgroundTaskLog.status == "completed"
            ).label("completed"),
            func.count(BackgroundTaskLog.id).filter(
                BackgroundTaskLog.status == "failed"
            ).label("failed"),
        )
        .where(*window_filter)
        .group_by("bucket")
        .order_by("bucket")
    )
    timeseries = [
        TimeseriesBucket(bucket=r.bucket, completed=r.completed, failed=r.failed)
        for r in ts_result.all()
    ]

    return WorkerHealthResponse(
        queue=QueueStats(pending=pending, running=running, throughput_per_hour=throughput),
        reliability=ReliabilityStats(
            total=total,
            succeeded=succeeded,
            failed=failed,
            failure_rate_pct=failure_rate,
            total_retries=total_retries,
            top_errors=top_errors,
        ),
        performance=PerformanceStats(by_task=by_task),
        timeseries=timeseries,
    )
```

Note: The router prefix is already `/workspaces/{workspace_id}` (line 24 of logs.py), so the endpoint path is just `/workers/health`.

- [ ] **Step 4: Run tests**

```bash
docker compose exec backend pytest tests/unit/test_worker_health.py -v
```

Expected: All PASS.

- [ ] **Step 5: Run existing logs tests to verify no regressions**

```bash
docker compose exec backend pytest tests/unit/test_logs_endpoints.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/logs.py backend/app/schemas/worker_health.py backend/tests/unit/test_worker_health.py
git commit -m "feat: add worker health endpoint with aggregated metrics"
```

---

### Task 13: Frontend workers tab

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api-functions.ts`
- Modify: `frontend/src/app/(dashboard)/logs/page.tsx`

- [ ] **Step 1: Add types**

In `frontend/src/lib/types.ts`, add:

```typescript
export interface WorkerHealthTopError {
  task_name: string;
  error: string;
  count: number;
}

export interface WorkerHealthTaskPerf {
  task_name: string;
  count: number;
  success_rate_pct: number;
  avg_duration_ms: number | null;
  p95_duration_ms: number | null;
  last_failure_at: string | null;
}

export interface WorkerHealthTimeseries {
  bucket: string;
  completed: number;
  failed: number;
}

export interface WorkerHealth {
  queue: {
    pending: number;
    running: number;
    throughput_per_hour: number;
  };
  reliability: {
    total: number;
    succeeded: number;
    failed: number;
    failure_rate_pct: number;
    total_retries: number;
    top_errors: WorkerHealthTopError[];
  };
  performance: {
    by_task: WorkerHealthTaskPerf[];
  };
  timeseries: WorkerHealthTimeseries[];
}
```

- [ ] **Step 2: Add API function**

In `frontend/src/lib/api-functions.ts`, add:

```typescript
import { WorkerHealth } from "./types";

export function getWorkerHealth(workspaceId: string, window: "1h" | "24h" | "7d" = "24h") {
  return api.get<WorkerHealth>(
    `/api/v1/workspaces/${workspaceId}/workers/health?window=${window}`,
  );
}
```

- [ ] **Step 3: Add Workers tab to logs page**

In `frontend/src/app/(dashboard)/logs/page.tsx`, add a "Workers" tab. When selected, it:

1. Calls `getWorkerHealth(workspaceId, window)` on mount and when window changes.
2. Renders 4 stat cards at the top:
   - Queue depth (`pending + running`)
   - Throughput/hr
   - Failure rate %
   - Avg duration (compute from `performance.by_task` weighted average)
3. Renders a Recharts `BarChart` with the `timeseries` data — green bars for completed, red for failed.
4. Renders a sortable table of task types from `performance.by_task`.
5. Adds 1h / 24h / 7d toggle buttons in the top-right.

Import Recharts components:
```typescript
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
```

- [ ] **Step 4: Test manually**

1. Open http://localhost:3001/logs
2. Click "Workers" tab
3. Verify stat cards, chart, and table render (may be empty if no recent tasks)
4. Toggle between 1h / 24h / 7d windows

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api-functions.ts frontend/src/app/\(dashboard\)/logs/page.tsx
git commit -m "feat: add Workers tab to logs page with health dashboard"
```

---

## Chunk 4: Integration Testing & Cleanup

### Task 14: Run full test suite

- [ ] **Step 1: Run backend tests**

```bash
docker compose exec backend pytest tests/ -v --timeout=60
```

Fix any failures.

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend && npm test
```

Fix any failures.

- [ ] **Step 3: Run linting**

```bash
make lint
```

Fix any lint issues.

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -u
git commit -m "fix: address test and lint issues from three-feature implementation"
```
