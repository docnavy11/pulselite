"""Outbound webhook delivery service."""

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.organizational import WorkspaceWebhook
from app.models.webhook_delivery import WebhookDelivery

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
