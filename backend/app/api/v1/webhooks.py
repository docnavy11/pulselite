import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.organizational import Agent, WorkspaceWebhook

router = APIRouter(tags=["webhooks"])

EVENT_TYPES = [
    "conversation.created",
    "conversation.escalated",
    "conversation.resolved",
    "message.feedback",
]


class WebhookCreate(BaseModel):
    url: str
    event_types: list[str] = ["conversation.created", "conversation.escalated"]
    secret: str | None = None


@router.get("/workspaces/{workspace_id}/webhooks")
async def list_webhooks(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(select(WorkspaceWebhook).where(WorkspaceWebhook.workspace_id == workspace_id))
    hooks = result.scalars().all()
    return [
        {
            "id": str(h.id),
            "url": h.url,
            "event_types": h.event_types,
            "is_active": h.is_active,
            "created_at": h.created_at.isoformat(),
        }
        for h in hooks
    ]


@router.post("/workspaces/{workspace_id}/webhooks", status_code=201)
async def create_webhook(
    body: WebhookCreate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    if not body.url.startswith("https://"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL must use HTTPS")
    invalid = [e for e in body.event_types if e not in EVENT_TYPES]
    if invalid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid event types: {invalid}")
    hook = WorkspaceWebhook(
        workspace_id=workspace_id,
        url=body.url,
        event_types=body.event_types,
        secret=body.secret,
    )
    db.add(hook)
    await db.commit()
    await db.refresh(hook)
    return {"id": str(hook.id), "url": hook.url, "event_types": hook.event_types, "is_active": hook.is_active}


@router.delete("/workspaces/{workspace_id}/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(
        select(WorkspaceWebhook).where(
            WorkspaceWebhook.id == webhook_id,
            WorkspaceWebhook.workspace_id == workspace_id,
        )
    )
    hook = result.scalar_one_or_none()
    if not hook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    await db.delete(hook)
    await db.commit()
