import logging
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import engine, get_db
from app.dependencies import get_workspace_admin
from app.models.knowledge import Chatbot, Chunk, Document
from app.models.organizational import Workspace
from app.services.system_info import get_python_version, get_uptime_seconds
from app.api.v1.public_chat import limiter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/test-chat-sse")
async def test_chat_sse():
    """Test actual handle_message inside EventSourceResponse."""
    import sys
    from sse_starlette.sse import EventSourceResponse
    from app.database import async_session_factory
    from app.models.knowledge import Chatbot
    from app.services.resolution_service import handle_message

    # Collect ALL events first (non-streaming), then yield them.
    # This tests if handle_message works at all inside an endpoint.
    print("[TEST-CHAT] collecting events...", file=sys.stderr, flush=True)
    events = []
    async with async_session_factory() as db:
        bot = (await db.execute(select(Chatbot).limit(1))).scalar_one()
        print(f"[TEST-CHAT] chatbot={bot.name}", file=sys.stderr, flush=True)
        async for event in handle_message(db, bot.workspace_id, bot, "wat zijn de stages"):
            events.append(event)
            if len(events) <= 3:
                print(f"[TEST-CHAT] event {len(events)}: {event.type}", file=sys.stderr, flush=True)
        await db.commit()
    print(f"[TEST-CHAT] collected {len(events)} events", file=sys.stderr, flush=True)

    async def gen():
        for event in events:
            yield f"event: {event.type}\ndata: test\n\n"

    from fastapi.responses import StreamingResponse as SR
    return SR(gen(), media_type="text/event-stream",
              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/health")
@limiter.limit("60/minute")
async def health_check(request: Request, db: AsyncSession = Depends(get_db)):
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

    # Celery worker connectivity
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        worker_keys = await r.keys("celery-task-meta-*")
        # Check if celery heartbeat exists (inspect.ping writes to Redis)
        celery_active = await r.exists("unacked_mutex")
        await r.aclose()
        checks["celery"] = "connected" if celery_active or worker_keys else "unknown"
    except Exception as exc:
        checks["celery"] = "unknown"
        logger.warning("Health check: could not verify Celery status — %s", exc)

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
