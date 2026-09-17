"""SSE event stream — replaces Socket.IO."""

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from app.realtime.events import subscribe

router = APIRouter()


@router.get("/events/stream")
async def workspace_event_stream(request: Request):
    workspace = request.state.workspace
    return StreamingResponse(
        subscribe(str(workspace.id)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
