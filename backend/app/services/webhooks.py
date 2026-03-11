"""Outbound webhook delivery service."""

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.database import async_session_factory
from app.models.organizational import WorkspaceWebhook
from app.services.encryption import decrypt_api_key

logger = logging.getLogger(__name__)


async def fire_event(workspace_id: uuid.UUID, event_type: str, payload: dict) -> None:
    """Fire all active webhooks for a workspace that subscribe to event_type."""
    async with async_session_factory() as session:
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
        body = json.dumps(
            {
                "event": event_type,
                "workspace_id": str(workspace_id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": payload,
            }
        )
        headers = {"Content-Type": "application/json"}
        if hook.secret:
            try:
                secret = decrypt_api_key(hook.secret)
            except Exception:
                # Fallback for legacy plaintext secrets stored before encryption was introduced
                secret = hook.secret
            sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers["X-Pulse-Signature"] = f"sha256={sig}"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(hook.url, content=body, headers=headers)
        except Exception as e:
            logger.warning(f"Webhook delivery failed for {hook.url}: {e}")
