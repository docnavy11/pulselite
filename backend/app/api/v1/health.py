import logging
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import engine, get_db
from app.dependencies import get_workspace_admin
from app.models.knowledge import Chatbot, Chunk, Document
from app.models.organizational import Workspace
from app.services.system_info import get_python_version, get_uptime_seconds

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    checks: dict[str, str] = {}
    healthy = True

    # Database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as exc:
        checks["database"] = "disconnected"
        checks["database_error"] = "PostgreSQL connection failed. Check server logs for details."
        logger.error("Health check: database unreachable at %s:%s — %s", settings.POSTGRES_HOST, settings.POSTGRES_PORT, exc)
        healthy = False

    # Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        await r.ping()
        await r.aclose()
        checks["redis"] = "connected"
    except Exception as exc:
        checks["redis"] = "disconnected"
        checks["redis_error"] = "Redis connection failed. Check server logs for details."
        logger.error("Health check: redis unreachable at %s:%s — %s", settings.REDIS_HOST, settings.REDIS_PORT, exc)
        healthy = False

    # AI configuration (advisory — not a hard failure)
    ai_configured = bool(settings.AI_API_KEY)
    checks["ai_configured"] = "yes" if ai_configured else "no"
    if not ai_configured:
        checks["ai_hint"] = "No AI_API_KEY set. Chatbots will not work until you configure an AI provider in .env or Settings > AI Models."

    status_code = 200 if healthy else 503
    return JSONResponse(
        content={"status": "healthy" if healthy else "degraded", "checks": checks},
        status_code=status_code,
    )


@router.get("/workspaces/{workspace_id}/system-health")
async def get_system_health(
    workspace_id: uuid.UUID,
    workspace=Depends(get_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only endpoint returning detailed system health information."""

    # --- Database health ---
    db_info: dict = {}
    try:
        pool = engine.sync_engine.pool
        db_info = {
            "status": "healthy",
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "pool_status": pool.status(),
        }
    except Exception as exc:
        logger.error("System health: failed to read DB pool stats — %s", exc)
        db_info = {"status": "unhealthy", "error": "Failed to read pool stats"}

    # --- Redis health ---
    redis_info: dict = {}
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        info_memory = await r.info("memory")
        info_clients = await r.info("clients")
        info_server = await r.info("server")
        await r.aclose()
        redis_info = {
            "status": "healthy",
            "used_memory_human": info_memory.get("used_memory_human", "unknown"),
            "connected_clients": info_clients.get("connected_clients", 0),
            "uptime_seconds": info_server.get("uptime_in_seconds", 0),
        }
    except Exception as exc:
        logger.error("System health: redis unreachable — %s", exc)
        redis_info = {"status": "unhealthy", "error": "Redis connection failed"}

    # --- System info ---
    system_info = {
        "python_version": get_python_version(),
        "uptime_seconds": round(get_uptime_seconds(), 1),
        "current_time": datetime.now(timezone.utc).isoformat(),
    }

    # --- Storage stats ---
    storage: dict = {}
    try:
        workspace_count = (await db.execute(select(func.count()).select_from(Workspace))).scalar_one()
        chatbot_count = (await db.execute(select(func.count()).select_from(Chatbot))).scalar_one()
        document_count = (await db.execute(select(func.count()).select_from(Document))).scalar_one()
        chunk_count = (await db.execute(select(func.count()).select_from(Chunk))).scalar_one()
        storage = {
            "workspaces": workspace_count,
            "chatbots": chatbot_count,
            "documents": document_count,
            "chunks": chunk_count,
        }
    except Exception as exc:
        logger.error("System health: failed to query storage stats — %s", exc)
        storage = {"error": "Failed to query storage stats"}

    return {
        "database": db_info,
        "redis": redis_info,
        "system": system_info,
        "storage": storage,
    }
