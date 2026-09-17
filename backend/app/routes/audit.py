"""Audit log routes."""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit_log import AuditLog

router = APIRouter()


@router.get("/settings/audit", response_class=HTMLResponse)
async def audit_logs(
    request: Request,
    action: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    query = select(AuditLog).where(AuditLog.workspace_id == workspace.id)
    if action:
        query = query.where(AuditLog.action == action)
    query = query.order_by(AuditLog.timestamp.desc()).limit(100)
    logs = (await db.execute(query)).scalars().all()
    return request.app.state.templates.TemplateResponse(
        "settings/audit.html",
        {
            "request": request,
            "logs": logs,
            "action_filter": action,
        },
    )
