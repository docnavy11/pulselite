"""Admin routes — system health, server logs, audit trail, retrieval logs."""
import os
import socket
import sys
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.intelligence import RetrievalLog
from app.models.knowledge import Chatbot, Chunk, Document, KnowledgeBase
from app.models.conversations import Conversation

router = APIRouter(prefix="/admin")

_TABS = [
    ("health", "System Health"),
    ("server-logs", "Server Logs"),
    ("audit", "Audit Trail"),
    ("retrievals", "Retrieval Logs"),
]


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_overview(
    request: Request,
    tab: str = Query("health"),
    level: str = Query(""),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    ctx: dict = {"request": request, "tab": tab, "tabs": _TABS, "level_filter": level}

    if tab == "health":
        # Storage counts
        ctx["doc_count"] = (await db.execute(select(func.count(Document.id)).where(Document.workspace_id == workspace.id))).scalar_one()
        ctx["chunk_count"] = (await db.execute(select(func.count(Chunk.id)).where(Chunk.workspace_id == workspace.id))).scalar_one()
        ctx["conv_count"] = (await db.execute(select(func.count(Conversation.id)).where(Conversation.workspace_id == workspace.id))).scalar_one()
        ctx["chatbot_count"] = (await db.execute(select(func.count(Chatbot.id)).where(Chatbot.workspace_id == workspace.id))).scalar_one()
        ctx["kb_count"] = (await db.execute(select(func.count(KnowledgeBase.id)).where(KnowledgeBase.workspace_id == workspace.id))).scalar_one()

        # Database connectivity + pool
        db_info: dict = {"connected": False}
        try:
            await db.execute(text("SELECT 1"))
            db_info["connected"] = True
            pool = db.bind.pool  # type: ignore[union-attr]
            db_info["pool_size"] = pool.size()
            db_info["pool_checked_in"] = pool.checkedin()
            db_info["pool_checked_out"] = pool.checkedout()
            db_info["pool_overflow"] = pool.overflow()
        except Exception:
            pass
        ctx["db_info"] = db_info

        # Redis
        redis_info: dict = {"connected": False}
        try:
            import redis.asyncio as aioredis
            from app.config import settings as cfg
            r = aioredis.from_url(cfg.redis_url)
            info = await r.info()
            await r.aclose()
            redis_info = {
                "connected": True,
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "uptime_in_seconds": info.get("uptime_in_seconds"),
            }
        except Exception:
            pass
        ctx["redis_info"] = redis_info

        # System
        start_time = getattr(request.app.state, "_start_time", None)
        uptime_str = None
        if start_time:
            delta = datetime.now(timezone.utc) - start_time
            hours, rem = divmod(int(delta.total_seconds()), 3600)
            mins = rem // 60
            uptime_str = f"{hours}h {mins}m"
        ctx["sys_info"] = {
            "python_version": sys.version.split()[0],
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "uptime": uptime_str,
        }

        # Worker + scheduler status
        worker_ok = False
        worker_queue_depth = 0
        try:
            from app.background.runner import _worker_task
            worker_ok = _worker_task is not None and not _worker_task.done()
            from app.models.background_job import BackgroundJob
            worker_queue_depth = (await db.execute(
                select(func.count()).select_from(BackgroundJob).where(BackgroundJob.status == "pending")
            )).scalar_one()
        except Exception:
            pass

        scheduler_jobs = 0
        scheduler_ok = False
        try:
            from app.background.scheduler import scheduler
            scheduler_ok = scheduler.running
            scheduler_jobs = len(scheduler.get_jobs())
        except Exception:
            pass

        ctx["worker_ok"] = worker_ok
        ctx["worker_queue_depth"] = worker_queue_depth
        ctx["scheduler_ok"] = scheduler_ok
        ctx["scheduler_jobs"] = scheduler_jobs

    elif tab == "server-logs":
        from app.services.log_buffer import LogBuffer
        buf = LogBuffer.get_instance()
        entries = buf.get_entries(limit=200, level=level or None)
        ctx["log_entries"] = list(reversed(entries))

    elif tab == "audit":
        limit = 50
        total = (await db.execute(
            select(func.count(AuditLog.id)).where(AuditLog.workspace_id == workspace.id)
        )).scalar_one()
        audit_logs = (await db.execute(
            select(AuditLog).where(AuditLog.workspace_id == workspace.id)
            .order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
        )).scalars().all()
        ctx["audit_logs"] = audit_logs
        ctx["audit_total"] = total
        ctx["audit_offset"] = offset
        ctx["audit_limit"] = limit

    elif tab == "retrievals":
        limit = 50
        total = (await db.execute(
            select(func.count(RetrievalLog.id)).where(RetrievalLog.workspace_id == workspace.id)
        )).scalar_one()
        rows = (await db.execute(
            select(RetrievalLog, Chatbot.name.label("chatbot_name"))
            .outerjoin(Chatbot, Chatbot.id == RetrievalLog.chatbot_id)
            .where(RetrievalLog.workspace_id == workspace.id)
            .order_by(RetrievalLog.created_at.desc())
            .limit(limit).offset(offset)
        )).all()
        ctx["retrieval_rows"] = rows
        ctx["retrieval_total"] = total
        ctx["retrieval_offset"] = offset
        ctx["retrieval_limit"] = limit

    return request.app.state.templates.TemplateResponse("admin/index.html", ctx)
