"""Centralized real-time event emission and state persistence.

Architecture (single-process deployment):
- API process: emits directly via the Socket.IO server instance.
- Celery workers: POST to /api/internal/emit on the API server.

All emitters also write active task state to Redis hashes so the
frontend can fetch a snapshot on page load via GET /realtime/state.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

# ── Process detection ────────────────────────────────────────────────────────

_is_api_process = False


def mark_api_process() -> None:
    """Called by main.py at import time."""
    global _is_api_process
    _is_api_process = True


def _get_sio() -> Any | None:
    """Get the Socket.IO server instance (only works in API process)."""
    if not _is_api_process:
        return None
    try:
        from app.main import sio
        return sio
    except Exception:
        return None


# ── Socket.IO emission ───────────────────────────────────────────────────────

async def _emit_via_http(event: str, data: dict, room: str) -> None:
    """Emit via the internal HTTP endpoint (Celery workers)."""
    import httpx

    url = "http://backend:8000/api/internal/emit"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                url,
                json={"event": event, "data": data, "room": room},
                headers={"X-Internal-Secret": settings.SECRET_KEY},
            )
            if resp.status_code != 200:
                logger.warning("Internal emit returned %s", resp.status_code)
    except Exception:
        logger.warning("Failed to emit %s via HTTP", event, exc_info=True)


async def emit_to_workspace(workspace_id: str, event: str, data: dict) -> None:
    """Emit a Socket.IO event to all clients in a workspace room.

    Safe to call from API server or Celery worker (async context required).
    """
    try:
        sio = _get_sio()
        if sio is not None:
            await sio.emit(event, data, room=workspace_id)
        else:
            await _emit_via_http(event, data, workspace_id)
    except Exception:
        logger.warning("Failed to emit %s to workspace %s", event, workspace_id, exc_info=True)


async def emit_task_event(
    workspace_id: str | uuid.UUID,
    event_type: str,
    task_name: str,
    task_id: str,
    detail: str | None = None,
    current: int | None = None,
    total: int | None = None,
    error: str | None = None,
) -> None:
    """Emit a task lifecycle event, persist state to Redis, and log to DB.

    event_type: "started", "progress", or "completed".
    """
    ws_id = str(workspace_id)
    data = {
        "task_name": task_name,
        "task_id": task_id,
        "detail": detail,
        "current": current,
        "total": total,
        "error": error,
    }

    # Persist state to Redis (ephemeral)
    if event_type == "started":
        await write_task_state(ws_id, task_id, task_name, "running", detail)
    elif event_type == "progress":
        await write_task_state(ws_id, task_id, task_name, "running", detail, current, total)
    elif event_type == "completed":
        await clear_task_state(ws_id, task_id)

    # Persist to DB (durable log)
    await _log_task_event(ws_id, event_type, task_name, task_id, detail, error)

    await emit_to_workspace(ws_id, f"task:{event_type}", data)


async def _log_task_event(
    workspace_id: str,
    event_type: str,
    task_name: str,
    task_id: str,
    detail: str | None,
    error: str | None,
) -> None:
    """Write task lifecycle events to the background_task_logs table."""
    try:
        from app.database import async_session_factory, engine
        from app.models.task_log import BackgroundTaskLog
        from datetime import datetime, timezone
        from sqlalchemy import select

        # Celery workers need a fresh pool (different event loop)
        if not _is_api_process:
            await engine.dispose()

        async with async_session_factory() as session:
            if event_type == "started":
                log = BackgroundTaskLog(
                    id=uuid.uuid4(),
                    workspace_id=uuid.UUID(workspace_id),
                    task_name=task_name,
                    task_id=task_id,
                    status="running",
                    detail=detail,
                )
                session.add(log)
                await session.commit()

            elif event_type == "completed":
                result = await session.execute(
                    select(BackgroundTaskLog).where(
                        BackgroundTaskLog.task_id == task_id,
                        BackgroundTaskLog.status == "running",
                    )
                )
                log = result.scalar_one_or_none()
                if log:
                    now = datetime.now(timezone.utc)
                    log.status = "failed" if error else "completed"
                    log.detail = detail or log.detail
                    log.error = error
                    log.completed_at = now
                    log.duration_ms = int((now - log.started_at).total_seconds() * 1000)
                    await session.commit()
                else:
                    # No matching "started" row — insert a completed record directly
                    log = BackgroundTaskLog(
                        id=uuid.uuid4(),
                        workspace_id=uuid.UUID(workspace_id),
                        task_name=task_name,
                        task_id=task_id,
                        status="failed" if error else "completed",
                        detail=detail,
                        error=error,
                        completed_at=datetime.now(timezone.utc),
                    )
                    session.add(log)
                    await session.commit()

            # "progress" events are not logged to DB (too noisy)
    except Exception:
        logger.warning("Failed to log task event to DB", exc_info=True)


# ── Redis state persistence ──────────────────────────────────────────────────
#
# Keys use the pattern:  rt:{workspace_id}:{category}:{id}
# All keys have a 1-hour TTL as a safety net for orphaned entries.
#
# Categories:
#   task    — generic background tasks (analyze, sentiment, etc.)
#   crawl   — active crawl jobs
#   doc     — documents being ingested
#   setup   — chatbot setup status (crawling/configuring)

_STATE_TTL = 3600  # 1 hour


def _redis_client() -> aioredis.Redis:
    """Create a fresh Redis client. Safe across event loops."""
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def _safe_redis(coro_fn):
    """Execute a Redis operation, silently swallowing errors."""
    try:
        r = _redis_client()
        try:
            return await coro_fn(r)
        finally:
            await r.aclose()
    except Exception:
        logger.warning("Redis state operation failed", exc_info=True)
        return None


# ── Task state ───────────────────────────────────────────────────────────────

async def write_task_state(
    workspace_id: str,
    task_id: str,
    task_name: str,
    status: str,
    detail: str | None = None,
    current: int | None = None,
    total: int | None = None,
) -> None:
    key = f"rt:{workspace_id}:task:{task_id}"
    value = json.dumps({
        "task_id": task_id,
        "task_name": task_name,
        "status": status,
        "detail": detail,
        "current": current,
        "total": total,
    })

    async def _write(r: aioredis.Redis):
        await r.set(key, value, ex=_STATE_TTL)

    await _safe_redis(_write)


async def clear_task_state(workspace_id: str, task_id: str) -> None:
    key = f"rt:{workspace_id}:task:{task_id}"

    async def _clear(r: aioredis.Redis):
        await r.delete(key)

    await _safe_redis(_clear)


# ── Crawl state ──────────────────────────────────────────────────────────────

async def write_crawl_state(workspace_id: str, job_id: str, state: dict) -> None:
    key = f"rt:{workspace_id}:crawl:{job_id}"
    value = json.dumps({"job_id": job_id, **state})

    async def _write(r: aioredis.Redis):
        await r.set(key, value, ex=_STATE_TTL)

    await _safe_redis(_write)


async def clear_crawl_state(workspace_id: str, job_id: str) -> None:
    key = f"rt:{workspace_id}:crawl:{job_id}"

    async def _clear(r: aioredis.Redis):
        await r.delete(key)

    await _safe_redis(_clear)


# ── Chatbot setup state ─────────────────────────────────────────────────────

async def write_chatbot_setup_state(
    workspace_id: str, chatbot_id: str, setup_status: str
) -> None:
    key = f"rt:{workspace_id}:setup:{chatbot_id}"
    value = json.dumps({"chatbot_id": chatbot_id, "setup_status": setup_status})

    async def _write(r: aioredis.Redis):
        await r.set(key, value, ex=_STATE_TTL)

    await _safe_redis(_write)


async def clear_chatbot_setup_state(workspace_id: str, chatbot_id: str) -> None:
    key = f"rt:{workspace_id}:setup:{chatbot_id}"

    async def _clear(r: aioredis.Redis):
        await r.delete(key)

    await _safe_redis(_clear)


# ── Document active state ───────────────────────────────────────────────────

async def write_document_active(
    workspace_id: str, document_id: str, title: str, kb_id: str, status: str
) -> None:
    key = f"rt:{workspace_id}:doc:{document_id}"
    value = json.dumps({
        "document_id": document_id,
        "title": title,
        "knowledge_base_id": kb_id,
        "status": status,
    })

    async def _write(r: aioredis.Redis):
        await r.set(key, value, ex=_STATE_TTL)

    await _safe_redis(_write)


async def clear_document_active(workspace_id: str, document_id: str) -> None:
    key = f"rt:{workspace_id}:doc:{document_id}"

    async def _clear(r: aioredis.Redis):
        await r.delete(key)

    await _safe_redis(_clear)


# ── State snapshot (used by GET /realtime/state endpoint) ────────────────────

async def get_workspace_realtime_state(workspace_id: str) -> dict:
    """Read all active state for a workspace from Redis."""
    prefix = f"rt:{workspace_id}:"

    async def _scan(r: aioredis.Redis):
        tasks = []
        crawls = []
        documents = []
        setups = []

        async for key in r.scan_iter(match=f"{prefix}*", count=100):
            raw = await r.get(key)
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # Categorize by key pattern
            suffix = key[len(prefix):]
            if suffix.startswith("task:"):
                tasks.append(entry)
            elif suffix.startswith("crawl:"):
                crawls.append(entry)
            elif suffix.startswith("doc:"):
                documents.append(entry)
            elif suffix.startswith("setup:"):
                setups.append(entry)

        return {
            "active_tasks": tasks,
            "active_crawls": crawls,
            "active_documents": documents,
            "chatbot_setup": setups,
        }

    result = await _safe_redis(_scan)
    return result or {
        "active_tasks": [],
        "active_crawls": [],
        "active_documents": [],
        "chatbot_setup": [],
    }
