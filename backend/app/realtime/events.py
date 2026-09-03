"""SSE-based real-time event system — replaces Socket.IO + Redis.

Subscribers connect via GET /events/stream. Background tasks push HTML
fragments (or JSON) to all subscribers in a workspace via notify_workspace().
"""
import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)


async def subscribe(workspace_id: str) -> AsyncGenerator[str, None]:
    """Yields SSE-formatted events for a workspace. Used by the events stream endpoint."""
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers[workspace_id].add(queue)
    try:
        while True:
            event = await queue.get()
            event_type = event.get("type", "message")
            data = event.get("data", "")
            # SSE format: multi-line data needs each line prefixed with "data: "
            if isinstance(data, dict):
                data = json.dumps(data)
            lines = data.split("\n")
            yield f"event: {event_type}\n" + "".join(f"data: {line}\n" for line in lines) + "\n"
    except asyncio.CancelledError:
        pass
    finally:
        _subscribers[workspace_id].discard(queue)


async def notify_workspace(workspace_id: str, event_type: str, data: str | dict):
    """Push an event to all SSE subscribers in a workspace."""
    queues = _subscribers.get(workspace_id, set())
    for queue in queues:
        try:
            queue.put_nowait({"type": event_type, "data": data})
        except asyncio.QueueFull:
            logger.warning("SSE queue full for workspace %s, dropping event", workspace_id)


def subscriber_count(workspace_id: str) -> int:
    return len(_subscribers.get(workspace_id, set()))
