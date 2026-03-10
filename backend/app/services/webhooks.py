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

from app.models.organizational import WorkspaceWebhook

logger = logging.getLogger(__name__)


async def fire_event(db: AsyncSession, workspace_id: uuid.UUID, event_type: str, payload: dict) -> None:
    """Fire all active webhooks for a workspace that subscribe to event_type."""
    result = await db.execute(
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
            sig = hmac.new(hook.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers["X-Pulse-Signature"] = f"sha256={sig}"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(hook.url, content=body, headers=headers)
        except Exception as e:
            logger.warning(f"Webhook delivery failed for {hook.url}: {e}")
