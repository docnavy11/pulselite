import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace, get_workspace_admin
from app.models.organizational import Agent, WorkspaceWebhook
from app.models.webhook_delivery import WebhookDelivery
from app.schemas.webhook_delivery import WebhookDeliveryListResponse, WebhookDeliveryResponse
from app.services.encryption import encrypt_api_key
from app.utils.url_validation import validate_url_not_private

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
    workspace_id: uuid.UUID = Depends(get_workspace_admin),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    if not body.url.startswith("https://"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL must use HTTPS")
    try:
        validate_url_not_private(body.url)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook URL: must not point to a private network")
    invalid = [e for e in body.event_types if e not in EVENT_TYPES]
    if invalid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid event types: {invalid}")
    hook = WorkspaceWebhook(
        workspace_id=workspace_id,
        url=body.url,
        event_types=body.event_types,
        secret=encrypt_api_key(body.secret) if body.secret else None,
    )
    db.add(hook)
    await db.commit()
    await db.refresh(hook)
    return {"id": str(hook.id), "url": hook.url, "event_types": hook.event_types, "is_active": hook.is_active, "created_at": hook.created_at.isoformat()}


class WebhookUpdate(BaseModel):
    url: str | None = None
    event_types: list[str] | None = None
    secret: str | None = None
    is_active: bool | None = None


@router.patch("/workspaces/{workspace_id}/webhooks/{webhook_id}")
async def update_webhook(
    body: WebhookUpdate,
    webhook_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace_admin),
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

    if body.url is not None:
        if not body.url.startswith("https://"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL must use HTTPS")
        try:
            validate_url_not_private(body.url)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook URL: must not point to a private network")
        hook.url = body.url

    if body.event_types is not None:
        invalid = [e for e in body.event_types if e not in EVENT_TYPES]
        if invalid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid event types: {invalid}")
        hook.event_types = body.event_types

    if body.secret is not None:
        hook.secret = encrypt_api_key(body.secret)

    if body.is_active is not None:
        hook.is_active = body.is_active

    await db.commit()
    await db.refresh(hook)
    return {
        "id": str(hook.id),
        "url": hook.url,
        "event_types": hook.event_types,
        "is_active": hook.is_active,
        "created_at": hook.created_at.isoformat(),
    }


@router.delete("/workspaces/{workspace_id}/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace_admin),
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

    from app.workers.tasks.deliver_webhook import deliver_webhook  # noqa: PLC0415
    deliver_webhook.delay(str(delivery_id))

    return delivery
