"""Audit log endpoints — admin-only, workspace-scoped."""
import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace_admin
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogListResponse, AuditLogResponse

router = APIRouter(prefix="/workspaces/{workspace_id}/audit-logs", tags=["audit"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    workspace_id: uuid.UUID = Depends(get_workspace_admin),
    db: AsyncSession = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    action: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    resource_type: Optional[str] = None,
    since: Optional[datetime] = None,
) -> AuditLogListResponse:
    """List audit log entries for the workspace, newest first."""
    filters = [AuditLog.workspace_id == workspace_id]
    if action:
        filters.append(AuditLog.action == action)
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if since:
        filters.append(AuditLog.timestamp >= since)

    total_result = await db.execute(select(func.count(AuditLog.id)).where(*filters))
    total = total_result.scalar_one()

    if total == 0:
        return AuditLogListResponse(items=[], total=0)

    rows_result = await db.execute(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [AuditLogResponse.model_validate(row) for row in rows_result.scalars()]
    return AuditLogListResponse(items=items, total=total)
