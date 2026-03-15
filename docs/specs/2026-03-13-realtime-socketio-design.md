# Real-time Events via Socket.IO — Design Spec

## Goal

Replace all frontend polling with Socket.IO push events. Show in-flux UI states (live progress, animated transitions) and toast notifications for completed/failed operations. Keep SSE for chat token streaming.

## Architecture

```
Celery worker ──emit──→ Redis pub/sub ──→ Socket.IO server ──→ browser
                                              ↑
                              FastAPI (ASGI middleware, /socket.io)
```

- **Transport:** Socket.IO over WebSocket with HTTP long-polling fallback
- **Adapter:** Redis adapter (`python-socketio[asyncio]` + `AsyncRedisManager`)
- **Rooms:** One room per workspace ID. All users in a workspace see the same events.
- **Auth:** JWT token sent on connect, verified server-side. Connection rejected if invalid.
- **Workers emit via Redis:** Celery workers use a standalone `socketio.AsyncRedisManager` to publish events through Redis without holding a WebSocket connection.

## What stays as SSE

| Endpoint | Reason |
|----------|--------|
| `POST /api/v1/public/chat` | Widget compatibility, token streaming |
| `POST /api/v1/chat` | Token streaming |
| `POST /api/v1/workspaces/{id}/copilot/chat` | Agentic token streaming |

These are request-response streams (one SSE per user message). Socket.IO doesn't improve them.

## Events

All events are emitted to the workspace room. Frontend filters by relevant IDs client-side.

### `crawl:progress`

Emitted during crawl execution as pages are discovered and fetched.

```json
{
  "job_id": "uuid",
  "chatbot_id": "uuid | null",
  "phase": "discovering | fetching",
  "pages_discovered": 11,
  "pages_queued": 5,
  "pages_failed": 0,
  "status": "running"
}
```

**Emit points:**
- `crawl_service.py` — after `job.phase = "discovering"`, after `job.phase = "fetching"`, after each `pages_queued += 1`
- `crawl_service.py` — on `job.status = "completed"` or `"failed"`

**Debounce:** `pages_queued` updates can be high-frequency. Emit at most every 1 second (batch in the emit helper).

### `crawl:completed`

Emitted when a crawl job finishes (success or failure).

```json
{
  "job_id": "uuid",
  "chatbot_id": "uuid | null",
  "status": "completed | failed",
  "pages_queued": 11,
  "pages_failed": 0,
  "error_message": null
}
```

**Emit point:** `crawl_service.py` — final status update before return.

### `document:status_changed`

Emitted when a document's ingestion status changes.

```json
{
  "document_id": "uuid",
  "knowledge_base_id": "uuid",
  "status": "processing | indexed | failed | skipped",
  "char_count": 1842,
  "title": "About — QIS",
  "error_message": null
}
```

**Emit points:**
- `pipeline.py` — `run_ingestion()` sets status to `"processing"` at start
- `pipeline.py` — sets status to `"indexed"` at end (with char_count, chunk_count)
- `pipeline.py` — sets status to `"failed"` or `"skipped"` on error/budget
- `ingest_document.py` — `_mark_document_failed()`
- `reindex_article.py` — after reindex completes

### `chatbot:status_changed`

Emitted when chatbot setup_status transitions.

```json
{
  "chatbot_id": "uuid",
  "setup_status": "crawling | configuring | ready | setup_failed"
}
```

**Emit points:**
- `crawl_service.py` — `chatbot.setup_status = "crawling"`
- `ingest_document.py` — atomic transition to `"configuring"`
- `run_autoconfig.py` — `"ready"` or `"setup_failed"`

### `workspace:usage_updated`

Emitted when `chars_indexed` changes (document indexed, deleted, or skipped).

```json
{
  "chars_indexed": 18609,
  "chars_limit": 500000,
  "plan": "free"
}
```

**Emit points:**
- `pipeline.py` — after char budget increment
- `document_service.py` — after `delete_document` releases chars
- `knowledge_base_service.py` — after KB delete releases chars
- `chatbot_service.py` — after chatbot delete releases chars

## Backend implementation

### New dependencies

```
python-socketio[asyncio]>=5.11
```

No additional Redis library needed — `python-socketio` uses the existing `redis` package.

### New file: `backend/app/services/realtime.py`

Centralized emit helper. All event emission goes through this module.

```python
import socketio

mgr = None  # initialized in main.py
sio = None  # initialized in main.py

def init(sio_server: socketio.AsyncServer, redis_url: str):
    """Called once from main.py."""
    global sio, mgr
    sio = sio_server
    # For workers: standalone manager that publishes via Redis
    mgr = socketio.AsyncRedisManager(redis_url, write_only=True)

async def emit_to_workspace(workspace_id: str, event: str, data: dict):
    """Emit from the API server process."""
    if sio:
        await sio.emit(event, data, room=workspace_id)

def emit_from_worker(workspace_id: str, event: str, data: dict):
    """Emit from a Celery worker (sync, via Redis pub/sub)."""
    import asyncio
    if mgr:
        # Workers create their own event loop via asyncio.run()
        # so we can await here within the worker's _run() coroutine
        loop = asyncio.get_event_loop()
        loop.create_task(mgr.emit(event, data, room=workspace_id))
```

Worker-side: since workers already run `asyncio.run(_run(...))`, the emit can be awaited inside the async `_run` function. A simpler approach:

```python
# In worker tasks, after db.commit():
from app.services.realtime import emit_to_workspace
await emit_to_workspace(str(workspace_id), "document:status_changed", {...})
```

The `AsyncRedisManager` in write-only mode publishes to Redis from any process. The Socket.IO server (in the API process) picks it up and delivers to connected clients.

### Changes to `backend/app/main.py`

```python
import socketio
from app.services.realtime import init as init_realtime

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[],  # handled by FastAPI CORS
    client_manager=socketio.AsyncRedisManager(settings.REDIS_URL),
)
init_realtime(sio, settings.REDIS_URL)

# Auth on connect
@sio.event
async def connect(sid, environ, auth):
    from app.services.auth_service import decode_access_token
    token = auth.get("token") if auth else None
    if not token:
        raise socketio.exceptions.ConnectionRefusedError("Missing token")
    try:
        user = decode_access_token(token)
    except Exception:
        raise socketio.exceptions.ConnectionRefusedError("Invalid token")
    await sio.save_session(sid, {"user_id": str(user.id)})

@sio.event
async def join_workspace(sid, data):
    workspace_id = data.get("workspace_id")
    # TODO: verify membership
    await sio.enter_room(sid, workspace_id)

@sio.event
async def leave_workspace(sid, data):
    workspace_id = data.get("workspace_id")
    sio.leave_room(sid, workspace_id)

# Mount as ASGI app
socket_app = socketio.ASGIApp(sio, other_app=app)
# In uvicorn startup: run socket_app instead of app
```

### Changes to worker tasks

Each task's async `_run()` function emits events after `db.commit()`:

**`crawl_service.py`** — emit `crawl:progress` after each phase change and page_queued increment. Emit `crawl:completed` at the end.

**`ingest_document.py`** — emit `document:status_changed` after ingestion. Emit `chatbot:status_changed` after the atomic configuring transition.

**`run_autoconfig.py`** — emit `chatbot:status_changed` with `"ready"` or `"setup_failed"`.

**`pipeline.py`** — emit `document:status_changed` at start (processing) and end (indexed/failed/skipped). Emit `workspace:usage_updated` after char budget changes.

## Frontend implementation

### New dependency

```
socket.io-client
```

### New file: `frontend/src/lib/socket.ts`

```typescript
import { io, Socket } from "socket.io-client";
import { useEffect, useRef } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (socket) return socket;
  const token = useAuthStore.getState().tokens?.access_token;
  socket = io(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000", {
    auth: { token },
    transports: ["websocket", "polling"],
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
  });
  return socket;
}

export function disconnectSocket() {
  socket?.disconnect();
  socket = null;
}

/**
 * Hook: subscribe to a Socket.IO event while the component is mounted.
 * Automatically joins/leaves workspace room.
 */
export function useSocketEvent<T = unknown>(
  event: string,
  handler: (data: T) => void,
  deps: unknown[] = [],
) {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    const s = getSocket();
    const workspace = useWorkspaceStore.getState().currentWorkspace;
    if (workspace) {
      s.emit("join_workspace", { workspace_id: workspace.id });
    }

    const listener = (data: T) => handlerRef.current(data);
    s.on(event, listener);

    return () => {
      s.off(event, listener);
    };
  }, [event, ...deps]);
}
```

### New file: `frontend/src/hooks/useRealtimeNotifications.ts`

Global hook mounted once in the dashboard layout. Shows toast notifications for completed events.

```typescript
import { useSocketEvent } from "@/lib/socket";
import { useToast } from "@/lib/toast";

export function useRealtimeNotifications() {
  const { success, error, info } = useToast();

  useSocketEvent<{status: string, pages_queued: number, error_message?: string}>(
    "crawl:completed",
    (data) => {
      if (data.status === "completed") {
        success(`Crawl completed — ${data.pages_queued} pages indexed`);
      } else {
        error(`Crawl failed: ${data.error_message || "Unknown error"}`);
      }
    }
  );

  useSocketEvent<{document_id: string, title: string, status: string, error_message?: string}>(
    "document:status_changed",
    (data) => {
      if (data.status === "failed") {
        error(`Failed to index: ${data.title} — ${data.error_message || "Unknown error"}`);
      }
      // Don't toast every successful index (too noisy during crawls)
    }
  );

  useSocketEvent<{chatbot_id: string, setup_status: string}>(
    "chatbot:status_changed",
    (data) => {
      if (data.setup_status === "ready") {
        success("Chatbot is ready for review");
      } else if (data.setup_status === "setup_failed") {
        error("Chatbot auto-configuration failed");
      }
    }
  );
}
```

Mount in `frontend/src/app/(dashboard)/layout.tsx`.

### In-flux UI states

**SourcesTab — live document updates:**
- `useSocketEvent("document:status_changed", ...)` — update doc in local state, animate status badge transition
- `useSocketEvent("crawl:progress", ...)` — show crawl banner with live progress: "Crawling — 5 of 11 pages fetched"
- `useSocketEvent("workspace:usage_updated", ...)` — update char usage bar with CSS transition
- New documents from crawl appear in the list as `document:status_changed` fires for each (status: "processing" → "indexed")

**Chatbots list — setup progress:**
- `useSocketEvent("chatbot:status_changed", ...)` — update chatbot card badge in real-time
- `useSocketEvent("crawl:progress", ...)` — show progress on the chatbot card during wizard

**Setup wizard — live crawl + autoconfig:**
- `useSocketEvent("crawl:progress", ...)` — live page counter, phase indicator
- `useSocketEvent("crawl:completed", ...)` — auto-advance to next step
- `useSocketEvent("chatbot:status_changed", ...)` — show "configuring" spinner, then auto-navigate to review when "ready"

**Visual patterns for in-flux states:**
- **Pulsing dot** (existing pattern) for "processing" — keep it
- **Counting up animation** for page counts during crawl (CSS `transition: all 0.3s`)
- **Progress bar** for crawl: `pages_queued / pages_discovered` as a thin progress bar
- **Skeleton shimmer** on new document rows appearing from a crawl before title is known
- **Status badge transitions** — fade between colors as status changes (green pulse when indexed)

### Polling removal

After Socket.IO events are wired up, remove all `setInterval` polling from:
- `chatbots/page.tsx` (lines 50, 134-136)
- `chatbots/[id]/setup/page.tsx` (lines 86-116, 118-142)
- `chatbots/[id]/sources/SourcesTab.tsx` (lines 107-126)
- `panels/CrawlStatusPanel.tsx` (lines 52-63)

Keep a **fallback refetch** on Socket.IO reconnect (`socket.on("connect", refetch)`) to sync state after disconnections.

## Notification summary

| Event | Toast | In-flux UI |
|-------|-------|-----------|
| `crawl:progress` | — | Live page counter, progress bar |
| `crawl:completed` | "Crawl completed — N pages" | Progress bar fills, stops |
| `crawl:completed` (failed) | "Crawl failed: reason" | Error state |
| `document:status_changed` (indexed) | — (too noisy) | Row appears/updates, green pulse |
| `document:status_changed` (failed) | "Failed to index: title" | Red badge |
| `chatbot:status_changed` (ready) | "Chatbot ready for review" | Auto-navigate to review |
| `chatbot:status_changed` (setup_failed) | "Auto-config failed" | Error state |
| `workspace:usage_updated` | — | Char bar animates |

## Docker / deployment

- `backend/Dockerfile` — no change, `python-socketio` is a pip dependency
- `docker-compose.yml` — no change, Redis already exposed
- Uvicorn runs the combined ASGI app (`socketio.ASGIApp(sio, app)`)
- Celery workers need `python-socketio` installed (already in same image) for `AsyncRedisManager` write-only mode
