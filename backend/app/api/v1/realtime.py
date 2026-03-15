import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_workspace
from app.models.task_log import BackgroundTaskLog
from app.services.realtime import get_workspace_realtime_state

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["realtime"])


@router.get("/realtime/state")
async def get_realtime_state(
    workspace_id: uuid.UUID = Depends(get_workspace),
):
    """Return a snapshot of all active real-time state for a workspace."""
    return await get_workspace_realtime_state(str(workspace_id))


@router.get("/realtime/logs")
async def get_task_logs(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    task_name: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    """Return paginated background task execution logs."""
    query = (
        select(BackgroundTaskLog)
        .where(BackgroundTaskLog.workspace_id == workspace_id)
        .order_by(BackgroundTaskLog.created_at.desc())
    )
    count_query = (
        select(func.count())
        .select_from(BackgroundTaskLog)
        .where(BackgroundTaskLog.workspace_id == workspace_id)
    )

    if task_name:
        query = query.where(BackgroundTaskLog.task_name == task_name)
        count_query = count_query.where(BackgroundTaskLog.task_name == task_name)
    if status:
        query = query.where(BackgroundTaskLog.status == status)
        count_query = count_query.where(BackgroundTaskLog.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(query.offset(offset).limit(limit))
    logs = result.scalars().all()

    return {
        "items": [
            {
                "id": str(log.id),
                "task_name": log.task_name,
                "task_id": log.task_id,
                "status": log.status,
                "detail": log.detail,
                "error": log.error,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                "duration_ms": log.duration_ms,
            }
            for log in logs
        ],
        "total": total,
    }
