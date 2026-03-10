import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import IntegrationConfig

logger = logging.getLogger(__name__)


async def _get_hubspot_config(session: AsyncSession, workspace_id: uuid.UUID) -> dict | None:
    result = await session.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "hubspot",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    config = result.scalar_one_or_none()
    return config.config if config else None


async def push_lead_to_hubspot(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    email: str | None,
    name: str | None,
    properties: dict | None = None,
) -> bool:
    config = await _get_hubspot_config(session, workspace_id)
    if not config or not config.get("api_key") or not email:
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            parts = (name or "").split(" ", 1)
            payload = {
                "properties": {
                    "email": email,
                    "firstname": parts[0],
                    "lastname": parts[1] if len(parts) > 1 else "",
                    **(properties or {}),
                }
            }
            resp = await client.post(
                "https://api.hubapi.com/crm/v3/objects/contacts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/json",
                },
            )
            return resp.status_code in (200, 201, 409)  # 409 = already exists
    except Exception as e:
        logger.error(f"HubSpot push failed: {e}")
        return False
