import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cryptography.fernet import Fernet

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.integrations import IntegrationConfig
from app.models.organizational import Agent

SENSITIVE_FIELDS = {"webhook_url", "api_key", "access_token", "api_token", "client_secret", "secret_key"}

router = APIRouter(prefix="/workspaces/{workspace_id}/integrations", tags=["integrations"])

VALID_TYPES = {
    "slack",
    "slack_bot",
    "email",
    "hubspot",
    "jira",
    "linear",
    "notion",
    "whatsapp",
    "messenger",
    "instagram",
    "shopify",
    "google_drive",
    "zendesk",
    "stripe",
    "salesforce",
    "dropbox",
}


class IntegrationConfigUpdate(BaseModel):
    config: dict
    is_active: bool = True


@router.get("")
async def list_integrations(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(select(IntegrationConfig).where(IntegrationConfig.workspace_id == workspace_id))
    configs = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "integration_type": c.integration_type,
            "service": c.integration_type,  # frontend alias
            "config": {
                k: "***" if "key" in k.lower() or "token" in k.lower() or "secret" in k.lower() else v
                for k, v in c.config.items()
            },
            "is_active": c.is_active,
            "is_connected": c.is_active,  # frontend alias
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in configs
    ]


@router.put("/{integration_type}")
async def update_integration(
    integration_type: str,
    body: IntegrationConfigUpdate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    if integration_type not in VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid type. Must be one of: {VALID_TYPES}"
        )

    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == integration_type,
        )
    )
    config = result.scalar_one_or_none()

    encrypted_config = dict(body.config)
    if settings.FERNET_KEY:
        f = Fernet(settings.FERNET_KEY.encode())
        for key in SENSITIVE_FIELDS:
            if key in encrypted_config and encrypted_config[key]:
                encrypted_config[key] = f.encrypt(encrypted_config[key].encode()).decode()

    if config:
        config.config = encrypted_config
        config.is_active = body.is_active
    else:
        config = IntegrationConfig(
            workspace_id=workspace_id,
            integration_type=integration_type,
            config=encrypted_config,
            is_active=body.is_active,
        )
        db.add(config)

    await db.commit()
    return {"status": "ok", "integration_type": integration_type}


@router.post("/{integration_type}/test")
async def test_integration(
    integration_type: str,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    if integration_type not in VALID_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid integration type")

    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == integration_type,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not configured")

    success = False
    detail = ""

    if integration_type == "slack":
        try:
            from slack_sdk.webhook import WebhookClient

            webhook_url = config.config.get("webhook_url")
            if not webhook_url:
                detail = "Missing webhook_url"
            else:
                webhook = WebhookClient(webhook_url)
                response = webhook.send(text="Pulse test connection successful!")
                success = response.status_code == 200
                detail = "Connected" if success else f"Failed: {response.status_code}"
        except Exception as e:
            detail = str(e)

    elif integration_type == "hubspot":
        try:
            from hubspot import HubSpot

            client = HubSpot(access_token=config.config.get("access_token"))
            client.crm.contacts.basic_api.get_page(limit=1)
            success = True
            detail = "Connected"
        except Exception as e:
            detail = str(e)

    elif integration_type == "email":
        success = bool(config.config.get("api_key"))
        detail = "API key configured" if success else "Missing api_key"

    elif integration_type in ("jira", "linear"):
        required = {"jira": ["server", "email", "api_token", "project_key"], "linear": ["api_key", "team_id"]}
        missing = [k for k in required.get(integration_type, []) if k not in config.config]
        success = len(missing) == 0
        detail = "Configured" if success else f"Missing: {', '.join(missing)}"

    return {"success": success, "detail": detail}


@router.delete("/{integration_type}")
async def delete_integration(
    integration_type: str,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    if integration_type not in VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid type. Must be one of: {VALID_TYPES}"
        )
    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == integration_type,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    config.is_active = False
    await db.commit()
    return {"status": "ok"}
