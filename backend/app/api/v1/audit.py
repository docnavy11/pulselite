import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace
from app.models.audit import AuditLog

router = APIRouter(prefix="/workspaces/{workspace_id}/audit-logs", tags=["audit"])


class AuditLogEntryResponse(BaseModel):
    id: uuid.UUID
    action: str
    actor_email: str | None
    resource_type: str | None
    resource_id: str | None
    resource_name: str | None
    ip_address: str | None
    created_at: str

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntryResponse]
    total: int


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    workspace_id: uuid.UUID = Depends(get_workspace),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    filters = [AuditLog.workspace_id == workspace_id]
    if action:
        filters.append(AuditLog.action == action)

    # Count total
    count_q = select(func.count()).select_from(AuditLog).where(*filters)
    total = (await db.execute(count_q)).scalar_one()

    # Fetch page
    items_q = select(AuditLog).where(*filters).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(items_q)).scalars().all()

    entries = [
        AuditLogEntryResponse(
            id=row.id,
            action=row.action,
            actor_email=row.actor_email,
            resource_type=row.resource_type,
            resource_id=str(row.resource_id) if row.resource_id else None,
            resource_name=row.resource_name,
            ip_address=row.ip_address,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]

    return AuditLogListResponse(items=entries, total=total)
