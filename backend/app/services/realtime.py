"""Centralized Socket.IO event emission.

All real-time events go through this module. Works from both the API server
process and Celery workers via Redis pub/sub (AsyncRedisManager write-only).
"""
import logging

import socketio

from app.config import settings

logger = logging.getLogger(__name__)

_mgr: socketio.AsyncRedisManager | None = None


def _get_manager() -> socketio.AsyncRedisManager | None:
    global _mgr
    if _mgr is None:
        try:
            _mgr = socketio.AsyncRedisManager(settings.REDIS_URL, write_only=True)
        except Exception:
            logger.warning("Failed to initialize Socket.IO Redis manager", exc_info=True)
            return None
    return _mgr


async def emit_to_workspace(workspace_id: str, event: str, data: dict) -> None:
    """Emit an event to all clients in a workspace room.

    Safe to call from API server or Celery worker (async context required).
    Silently no-ops if Redis is unavailable.
    """
    mgr = _get_manager()
    if mgr is None:
        return
    try:
        await mgr.emit(event, data, room=workspace_id)
    except Exception:
        logger.warning("Failed to emit %s to workspace %s", event, workspace_id, exc_info=True)
