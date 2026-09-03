"""Outbound webhook delivery service — uses background runner instead of Celery."""
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
from app.background.runner import enqueue

logger = logging.getLogger(__name__)


async def fire_event(
    workspace_id: uuid.UUID, event_type: str, payload: dict,
    db_session: AsyncSession | None = None,
) -> None:
    pending_ids = []

    async def _inner(session):
        result = await session.execute(
            select(WorkspaceWebhook).where(WorkspaceWebhook.workspace_id == workspace_id, WorkspaceWebhook.is_active == True)
        )
        hooks = result.scalars().all()
        for hook in hooks:
            if event_type not in (hook.event_types or []):
                continue
            delivery = WebhookDelivery(
                id=uuid.uuid4(), workspace_id=workspace_id, webhook_id=hook.id, event_type=event_type,
                payload={"event": event_type, "workspace_id": str(workspace_id), "timestamp": datetime.now(timezone.utc).isoformat(), "data": payload},
                status="pending",
            )
            session.add(delivery)
            await session.flush()
            pending_ids.append(delivery.id)

    if db_session is not None:
        await _inner(db_session)
    else:
        async with async_session_factory() as session:
            await _inner(session)
            await session.commit()

    for did in pending_ids:
        enqueue(_deliver_one(did), name=f"webhook:{did}")


async def _deliver_one(delivery_id: uuid.UUID):
    """Deliver a single webhook with retry logic."""
    import httpx
    from app.database import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(
            select(WebhookDelivery, WorkspaceWebhook)
            .join(WorkspaceWebhook, WebhookDelivery.webhook_id == WorkspaceWebhook.id)
            .where(WebhookDelivery.id == delivery_id)
        )
        row = result.one_or_none()
        if not row:
            return
        delivery, webhook = row

        import json
        body = json.dumps(delivery.payload, sort_keys=True, separators=(",", ":"))
        headers = {"Content-Type": "application/json"}
        if webhook.secret:
            sig = hmac.new(webhook.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers["X-PulseLite-Signature"] = f"sha256={sig}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(webhook.url, content=body, headers=headers)
            delivery.last_status_code = r.status_code
            delivery.status = "delivered" if r.is_success else "failed"
            delivery.attempts += 1
        except Exception as exc:
            delivery.last_error = str(exc)[:500]
            delivery.status = "failed"
            delivery.attempts += 1

        await db.commit()


def build_signature(secret: str, body: str) -> str:
    return f"sha256={hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()}"
