import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

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
        checks["database_error"] = f"Cannot reach PostgreSQL at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}. Check POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, and POSTGRES_PASSWORD in your .env file."
        logger.warning("Health check: database unreachable — %s", exc)
        healthy = False

    # Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        await r.ping()
        await r.aclose()
        checks["redis"] = "connected"
    except Exception as exc:
        checks["redis"] = "disconnected"
        checks["redis_error"] = f"Cannot reach Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}. Celery workers, real-time events, and token refresh will not work. Check REDIS_HOST and REDIS_PORT in your .env file."
        logger.warning("Health check: redis unreachable — %s", exc)
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
