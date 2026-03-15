# Single-Container Light Version — Design Spec

## Overview

An alternative Docker image (`pulselite/light`) that runs the entire PulseLite stack in a single container: Redis, uvicorn, Celery worker, Celery beat, and pre-built frontend static files — managed by supervisord. Only external dependency is PostgreSQL.

Minimal application code changes (config + static mount + one URL fix). Same codebase builds both the multi-container dev/SaaS setup and the single-container light image.

## Motivation

Self-hosted simplicity. Users run one container + Postgres and have a fully functional chatbot platform — no Docker Compose orchestration, no Redis to manage, no separate frontend server.

## Architecture

```
┌─────────────────────────────────────┐
│  pulselite/light container          │
│                                     │
│  supervisord (PID 1)                │
│  ├── redis-server (port 6379)       │
│  ├── uvicorn (port 8000)            │
│  ├── celery worker                  │
│  └── celery beat                    │
│                                     │
│  /app/static/ ← pre-built frontend │
│                                     │
│  Requires: external PostgreSQL      │
└─────────────────────────────────────┘
```

- **Postgres remains external** — stateful data belongs outside the app container. Users provide individual `POSTGRES_*` env vars.
- **Redis is internal** — ephemeral data only (task queue, real-time state, JWT refresh tokens, distributed locks). No persistence. Container restart = users re-login, in-flight tasks restart via Celery `acks_late`.
- **Frontend** — built at image build time (`npm run build`), served as static files by FastAPI. No Node.js at runtime.
- **Single port** — `8000` serves both API and frontend.

## File Changes

### New files

| File | Purpose |
|------|---------|
| `Dockerfile.light` | Multi-stage build: frontend → Python deps → final image with Redis + supervisord |
| `infra/light/supervisord.conf` | Process definitions for redis, uvicorn, celery worker, celery beat |
| `infra/light/entrypoint.sh` | Wait for Postgres, run alembic migrations, exec supervisord |
| `infra/light/redis.conf` | Minimal config: no persistence, `maxmemory 128mb`, `bind 127.0.0.1` |
| `backend/app/static_files.py` | Mount built frontend at `/` with SPA fallback for react-router |
| `docker-compose.light.yml` | Minimal compose: postgres + pulselite (convenience for users) |

### Modified files

| File | Change |
|------|--------|
| `backend/app/config.py` | Add `serve_frontend: bool = False` and `INTERNAL_API_URL: str = "http://backend:8000"` |
| `backend/app/main.py` | Conditional: if `serve_frontend`, mount static files handler (at bottom, after all API routes) |
| `backend/app/services/realtime.py` | Use `settings.INTERNAL_API_URL` instead of hardcoded `http://backend:8000` |

## Dockerfile.light

Three-stage build:

### Stage 1 — Frontend build
- Base: `node:20-alpine`
- Copy `frontend/`, run `npm ci && npm run build`
- Output: `/app/frontend/dist/`

### Stage 2 — Python dependencies
- Base: `python:3.12-slim`
- Install Python dependencies from `backend/pyproject.toml`

### Stage 3 — Final image
- Base: `python:3.12-slim`
- `apt-get install redis-server supervisor postgresql-client` (~10MB)
- Copy Python deps from stage 2
- Copy built frontend from stage 1 into `/app/static/`
- Copy backend source, infra/light/ configs
- `EXPOSE 8000`
- `ENTRYPOINT ["bash", "infra/light/entrypoint.sh"]`

Note: `postgresql-client` is needed for `pg_isready` in the entrypoint script.

## Entrypoint Script

`infra/light/entrypoint.sh`:

1. Wait for Postgres to be reachable (`pg_isready` loop, max 30 attempts, 1s sleep between)
2. Run `alembic upgrade head` (auto-migrate on every startup)
3. `exec supervisord -c /app/infra/light/supervisord.conf`

## Supervisord Configuration

`infra/light/supervisord.conf`:

```ini
[supervisord]
nodaemon=true
logfile=/dev/null
logfile_maxbytes=0

[program:redis]
command=redis-server /app/infra/light/redis.conf
autorestart=true
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
redirect_stderr=true
priority=10
startsecs=1

[program:uvicorn]
command=uvicorn app.main:combined_app --host 0.0.0.0 --port 8000
directory=/app/backend
autorestart=true
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
redirect_stderr=true
priority=20
startsecs=3

[program:celery-worker]
command=celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
directory=/app/backend
autorestart=true
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
redirect_stderr=true
priority=30
startsecs=5
stopwaitsecs=30

[program:celery-beat]
command=celery -A app.workers.celery_app beat --loglevel=info
directory=/app/backend
autorestart=true
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
redirect_stderr=true
priority=35
startsecs=5
```

**Key decisions:**
- **No `environment=` directives** — supervisord inherits the container's environment variables by default when `environment=` is absent. The entrypoint and compose set all env vars at the container level (`SERVE_FRONTEND`, `REDIS_HOST`, `INTERNAL_API_URL`, etc.) so they propagate to all child processes automatically.
- **`startsecs`** — Redis gets 1s, uvicorn 3s, workers 5s. This ensures Redis is ready before workers try to connect.
- **`stopwaitsecs=30`** on the worker — gives long-running tasks (crawl, ingestion) time to finish on graceful shutdown. Celery's `acks_late=True` means unfinished tasks return to the queue.
- **Priority 35 for beat** — starts after the worker to avoid scheduling tasks before a worker is available.

## Redis Configuration

`infra/light/redis.conf`:

```
bind 127.0.0.1
port 6379
maxmemory 128mb
maxmemory-policy allkeys-lru
save ""
appendonly no
loglevel warning
```

No persistence (`save ""`, `appendonly no`). Memory-capped at 128MB with LRU eviction. Bound to localhost only (not exposed outside container).

## Static File Serving

`backend/app/static_files.py`:

```python
from pathlib import Path
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

STATIC_DIR = Path("/app/static")
ASSETS_DIR = STATIC_DIR / "assets"


def mount_frontend(app):
    if not STATIC_DIR.exists():
        return

    # Serve Vite build assets with proper MIME types and caching
    if ASSETS_DIR.exists():
        app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="static-assets")

    # SPA fallback: serve index.html for all unmatched GET routes
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
```

Mounted **last** on the app, so all API routes (`/api/v1/*`, `/socket.io/*`) take priority. Vite `assets/` directory is served via `StaticFiles` for proper MIME types and caching headers. Any other unmatched GET falls through to the SPA handler, which serves `index.html` for client-side routing.

**Note:** Unregistered API paths hit via GET will return `index.html` instead of a JSON 404. This is standard SPA behavior and acceptable — API routes are all prefixed with `/api/`.

**In `main.py`** (at the bottom, after all router includes):

```python
if settings.serve_frontend:
    from app.static_files import mount_frontend
    mount_frontend(application)
```

**In `config.py`**:

```python
serve_frontend: bool = False
```

Defaults to `false` — no impact on the multi-container setup. Set to `true` at container level in the light image.

## Realtime HTTP Emit Fix

`backend/app/services/realtime.py` currently hardcodes:

```python
url = "http://backend:8000/api/internal/emit"
```

This hostname resolves in the multi-container Docker network but not inside a single container. Change to:

```python
url = f"{settings.INTERNAL_API_URL}/api/internal/emit"
```

**In `config.py`**:

```python
INTERNAL_API_URL: str = "http://backend:8000"
```

Default preserves current multi-container behavior. The light compose sets `INTERNAL_API_URL=http://127.0.0.1:8000`.

## docker-compose.light.yml

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: pulse
      POSTGRES_USER: pulse
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pulse"]
      interval: 5s
      timeout: 5s
      retries: 5

  pulselite:
    build:
      context: .
      dockerfile: Dockerfile.light
    ports:
      - "8000:8000"
    environment:
      - POSTGRES_HOST=postgres
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-changeme}
      - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY:-change-me-in-production}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - REDIS_HOST=127.0.0.1
      - SERVE_FRONTEND=true
      - INTERNAL_API_URL=http://127.0.0.1:8000
      - FRONTEND_URL=http://localhost:8000
      - BACKEND_CORS_ORIGINS=["http://localhost:8000"]
    volumes:
      - uploads_data:/app/backend/uploads
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  postgres_data:
  uploads_data:
```

Usage:
```bash
OPENROUTER_API_KEY=sk-... docker compose -f docker-compose.light.yml up -d
# Open http://localhost:8000
```

**Standalone Docker run** (no compose):
```bash
docker run -d \
  -p 8000:8000 \
  -e POSTGRES_HOST=host.docker.internal \
  -e POSTGRES_PASSWORD=yourpassword \
  -e SECRET_KEY=your-secret \
  -e JWT_SECRET_KEY=your-jwt-secret \
  -e OPENROUTER_API_KEY=sk-... \
  -e REDIS_HOST=127.0.0.1 \
  -e SERVE_FRONTEND=true \
  -e INTERNAL_API_URL=http://127.0.0.1:8000 \
  -e FRONTEND_URL=http://localhost:8000 \
  -v pulselite-uploads:/app/backend/uploads \
  pulselite/light
```

## Environment Variables

All env vars set at the **container level** (compose `environment:` or `docker run -e`). Supervisord inherits them automatically — no per-program `environment=` overrides.

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `POSTGRES_HOST` | Yes | `localhost` | Set to `postgres` in compose, or your DB host |
| `POSTGRES_PASSWORD` | Yes | `pulse_dev_password` | Must match Postgres |
| `SECRET_KEY` | Yes | none | App secret for internal auth |
| `JWT_SECRET_KEY` | Yes | none | JWT signing key |
| `OPENROUTER_API_KEY` | For chat | `""` | LLM provider key |
| `REDIS_HOST` | Yes | `localhost` | Set to `127.0.0.1` (embedded Redis) |
| `SERVE_FRONTEND` | Yes | `false` | Set to `true` in light image |
| `INTERNAL_API_URL` | Yes | `http://backend:8000` | Set to `http://127.0.0.1:8000` in light |
| `FRONTEND_URL` | Recommended | `http://localhost:3001` | Set to `http://localhost:8000` in light |
| `BACKEND_CORS_ORIGINS` | Recommended | `["http://localhost:3000"]` | Set to `["http://localhost:8000"]` in light |

Optional vars (`POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`) have sensible defaults in `config.py` and only need overriding for non-default setups.

## What Doesn't Change

- All Celery tasks and beat schedule
- All frontend React code
- RAG pipeline, ingestion, crawl, intelligence
- Socket.IO server and client
- Auth flow (JWT, OAuth, SSO)
- Database schema and migrations
- Test suite (unit, integration, e2e)
- Existing `Dockerfile`, `docker-compose.yml`, `Makefile`

**Minimal app changes** (3 files, backward-compatible):
- `config.py` — 2 new fields with defaults matching current behavior
- `main.py` — 3-line conditional at the bottom
- `realtime.py` — 1 line: use configurable URL instead of hardcoded hostname

## Known Limitations

- **Celery beat schedule file** — `celerybeat-schedule` is ephemeral (recreated on restart). Periodic tasks may fire once on container restart. This is acceptable.
- **Uploads volume** — User-uploaded files (PDFs, etc.) need a persistent volume. The compose file includes `uploads_data` for this. Standalone `docker run` users must mount a volume at `/app/backend/uploads`.
- **Single worker process** — `--concurrency=2` means 2 task threads. Sufficient for light deployments. Heavy crawl loads may queue.

## Testing

- Build the light image: `docker build -f Dockerfile.light -t pulselite/light .`
- Run with compose: `docker compose -f docker-compose.light.yml up -d`
- Verify all 4 processes running: `docker exec <container> supervisorctl status`
- Verify frontend served at `http://localhost:8000`
- Verify API at `http://localhost:8000/api/docs`
- Verify crawl + ingest + chat flow works end-to-end
- Verify real-time events (crawl progress, chatbot status) reach the frontend
- Existing test suite runs unchanged against the multi-container setup

## Image Size Estimate

- Python 3.12 slim base: ~150MB
- Python deps (FastAPI, SQLAlchemy, sentence-transformers, etc.): ~400MB
- Frontend build output: ~5MB
- Redis server + supervisor + postgresql-client: ~10MB
- Total: ~600-800MB

The sentence-transformers embedding + reranker models are the bulk. A future optimization could download models at first run instead of baking them in.
