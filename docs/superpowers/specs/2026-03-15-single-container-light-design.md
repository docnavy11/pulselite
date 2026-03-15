# Single-Container Light Version — Design Spec

## Overview

An alternative Docker image (`pulselite/light`) that runs the entire PulseLite stack in a single container: Redis, uvicorn, Celery worker, Celery beat, and pre-built frontend static files — managed by supervisord. Only external dependency is PostgreSQL.

Zero application code changes. Same codebase builds both the multi-container dev/SaaS setup and the single-container light image.

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

- **Postgres remains external** — stateful data belongs outside the app container. Users provide `DATABASE_URL`.
- **Redis is internal** — ephemeral data only (task queue, real-time state, JWT refresh tokens, distributed locks). No persistence. Container restart = users re-login, in-flight tasks restart via Celery `acks_late`.
- **Frontend** — built at image build time (`npm run build`), served as static files by FastAPI `StaticFiles`. No Node.js at runtime.
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
| `backend/app/config.py` | Add `serve_frontend: bool = False` |
| `backend/app/main.py` | Conditional: if `serve_frontend`, mount static files handler (at bottom, after all API routes) |

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
- `apt-get install redis-server supervisor` (~8MB)
- Copy Python deps from stage 2
- Copy built frontend from stage 1 into `/app/static/`
- Copy backend source, infra/light/ configs
- `EXPOSE 8000`
- `ENTRYPOINT ["bash", "infra/light/entrypoint.sh"]`

## Entrypoint Script

`infra/light/entrypoint.sh`:

1. Wait for Postgres to be reachable (`pg_isready` loop, max 30 attempts)
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

[program:uvicorn]
command=uvicorn app.main:combined_app --host 0.0.0.0 --port 8000
directory=/app/backend
environment=SERVE_FRONTEND=true,REDIS_HOST=127.0.0.1
autorestart=true
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
redirect_stderr=true
priority=20

[program:celery-worker]
command=celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
directory=/app/backend
environment=REDIS_HOST=127.0.0.1
autorestart=true
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
redirect_stderr=true
priority=30

[program:celery-beat]
command=celery -A app.workers.celery_app beat --loglevel=info
directory=/app/backend
environment=REDIS_HOST=127.0.0.1
autorestart=true
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
redirect_stderr=true
priority=30
```

Process start order: redis first (priority 10), then uvicorn (20), then workers (30). Supervisord restarts any process that crashes.

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
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

STATIC_DIR = Path("/app/static")


def mount_frontend(app: FastAPI) -> None:
    if not STATIC_DIR.exists():
        return

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
```

Mounted **last** on the app, so all API routes (`/api/v1/*`, `/socket.io/*`) take priority. Any unmatched GET falls through to the SPA handler, which serves the matching static file or `index.html` for client-side routing.

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

Defaults to `false` — no impact on the multi-container setup. Set to `true` via supervisord environment in the light image.

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
      - DATABASE_URL=postgresql+asyncpg://pulse:${POSTGRES_PASSWORD:-changeme}@postgres:5432/pulse
      - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  postgres_data:
```

Usage:
```bash
OPENROUTER_API_KEY=sk-... docker compose -f docker-compose.light.yml up -d
# Open http://localhost:8000
```

## What Doesn't Change

Zero modifications to:

- All Python services, models, schemas, routes
- All Celery tasks and beat schedule
- All frontend React code
- RAG pipeline, ingestion, crawl, intelligence
- Socket.IO server and client
- Auth flow (JWT, OAuth, SSO)
- Database schema and migrations
- Test suite (unit, integration, e2e)
- Existing `Dockerfile`, `docker-compose.yml`, `Makefile`

## Testing

- Build the light image: `docker build -f Dockerfile.light -t pulselite/light .`
- Run with compose: `docker compose -f docker-compose.light.yml up -d`
- Verify all 4 processes running: `docker exec <container> supervisorctl status`
- Verify frontend served at `http://localhost:8000`
- Verify API at `http://localhost:8000/api/docs`
- Verify crawl + ingest + chat flow works end-to-end
- Existing test suite runs unchanged against the multi-container setup

## Image Size Estimate

- Python 3.12 slim base: ~150MB
- Python deps (FastAPI, SQLAlchemy, sentence-transformers, etc.): ~400MB
- Frontend build output: ~5MB
- Redis server + supervisor: ~8MB
- Total: ~600-800MB

The sentence-transformers embedding + reranker models are the bulk. A future optimization could download models at first run instead of baking them in.
