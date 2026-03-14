"""Centralized Socket.IO event emission.

Creates a fresh manager per emit to avoid stale event-loop references
in Celery workers (each asyncio.run() creates a new loop).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def _create_manager() -> Any | None:
    try:
        import socketio  # noqa: F811 — lazy import to avoid crash if not installed (e.g. worker image)

        return socketio.AsyncRedisManager(settings.REDIS_URL, write_only=True)
    except ImportError:
        logger.warning("python-socketio not installed, skipping emit")
        return None
    except Exception:
        logger.warning("Failed to initialize Socket.IO Redis manager", exc_info=True)
        return None


async def emit_to_workspace(workspace_id: str, event: str, data: dict) -> None:
    """Emit an event to all clients in a workspace room.

    Safe to call from API server or Celery worker (async context required).
    Silently no-ops if Redis is unavailable.
    """
    mgr = _create_manager()
    if mgr is None:
        return
    try:
        await mgr.emit(event, data, room=workspace_id)
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
    """Emit a generic task lifecycle event (started/progress/completed).

    Safe to call from API server or Celery worker async context.
    """
    await emit_to_workspace(
        str(workspace_id),
        f"task:{event_type}",
        {
            "task_name": task_name,
            "task_id": task_id,
            "detail": detail,
            "current": current,
            "total": total,
            "error": error,
        },
    )
