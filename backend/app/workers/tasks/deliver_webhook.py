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
from app.utils.url_validation import validate_url_not_private
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

RETRY_DELAYS = [60, 300, 900, 3600, 10800]  # ~4.2 hours total
RETRY_JITTER_SECONDS = 30  # random jitter to avoid thundering herd


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60, soft_time_limit=55, time_limit=60)
def deliver_webhook(self, delivery_id: str) -> dict:
    try:
        return asyncio.run(_deliver(uuid.UUID(delivery_id), self))
    except Exception:
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
            logger.error("WebhookDelivery %s not found", delivery_id)
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

        # Validate webhook URL is not targeting private/internal IPs (SSRF prevention)
        try:
            validate_url_not_private(hook.url)
        except ValueError as exc:
            delivery.status = "failed"
            delivery.last_error = f"SSRF validation failed: {exc}"
            await session.commit()
            logger.warning("Webhook %s blocked by SSRF validation: %s", hook.id, exc)
            return {"status": "failed", "detail": str(exc)}

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
            logger.warning("Webhook delivery %s exhausted retries", delivery_id)
            return {"status": "failed", "attempts": delivery.attempts}

        # Schedule retry with jitter to prevent thundering herd
        import random

        delay_idx = min(delivery.attempts - 1, len(RETRY_DELAYS) - 1)
        delay = RETRY_DELAYS[delay_idx] + random.randint(0, RETRY_JITTER_SECONDS)
        delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        await session.commit()

        raise task.retry(countdown=delay)
