# Pulse — Production Deployment Guide

This guide covers deploying Pulse to a production server. The Docker Compose stack used for development needs a few adjustments for production readiness.

## Prerequisites

- A Linux server (Ubuntu 22.04+ recommended) with Docker and Docker Compose installed
- A domain name with DNS pointed at the server
- An SSL certificate (Let's Encrypt via Certbot or a load balancer that terminates TLS)
- A managed PostgreSQL instance (recommended) or self-hosted Postgres with backups
- A managed Redis instance (Upstash, Railway Redis, or self-hosted)
- An OpenAI API key
- A Fernet key (see below)

## 1. Environment Variables

Copy `.env.example` to `.env` and fill in all values:

```bash
cp .env.example .env
```

**Required secrets to generate:**

```bash
# SECRET_KEY and JWT_SECRET_KEY — generate random strings
openssl rand -hex 32

# FERNET_KEY — for BYOK encryption
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Production-specific values:**

```env
# Point to your managed DB / Redis
POSTGRES_HOST=your-db-host.example.com
REDIS_URL=redis://your-redis-host:6379/0

# CORS — your actual frontend domain
BACKEND_CORS_ORIGINS=["https://app.yourdomain.com"]

# Frontend URLs — your actual domain
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_APP_URL=https://app.yourdomain.com
```

## 2. Docker Compose for Production

The dev `docker-compose.yml` binds ports directly and has no restart policy. For production, create a `docker-compose.prod.yml` override:

```yaml
services:
  backend:
    restart: always
    environment:
      - ENVIRONMENT=production
    # Remove port exposure if using a reverse proxy
    ports: []

  celery_worker:
    restart: always

  celery_beat:
    restart: always

  frontend:
    restart: always
    ports: []

  postgres:
    restart: always
    volumes:
      - pg_data:/var/lib/postgresql/data

  redis:
    restart: always
```

Run with both files:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 3. Reverse Proxy (Nginx)

Route traffic based on subdomain or path. Example with two subdomains:

```nginx
# API
server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE support (chat streaming)
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}

# Frontend
server {
    listen 443 ssl;
    server_name app.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3001;
        proxy_set_header Host $host;
    }
}
```

**Important:** The `proxy_buffering off` setting is required for SSE (streaming chat) to work correctly.

## 4. Database Migrations

Run migrations against production DB before starting the backend:

```bash
docker compose exec backend alembic upgrade head
```

Or as a one-off container:

```bash
docker compose run --rm backend alembic upgrade head
```

**Never** seed (`make seed`) against production — that creates test data.

## 5. Scaling

### Celery Workers

The default `docker-compose.yml` has one worker. For higher throughput:

```bash
docker compose up -d --scale celery_worker=3
```

Or use separate worker queues per task type (ingestion vs. analysis) by setting `CELERY_QUEUES` in the worker command.

### Backend (FastAPI / Uvicorn)

The backend runs a single Uvicorn process. For production, use Gunicorn to manage multiple workers:

```yaml
# In docker-compose.prod.yml
backend:
  command: gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

Rule of thumb: `workers = (2 × CPU_cores) + 1`

## 6. Stripe Webhooks

After enabling Stripe:

1. In Stripe Dashboard → Webhooks → Add endpoint: `https://api.yourdomain.com/api/v1/billing/webhook`
2. Select events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`
3. Copy the webhook signing secret into `STRIPE_WEBHOOK_SECRET`

## 7. Google OAuth

In Google Cloud Console → OAuth 2.0 credentials:
- Add authorized redirect URI: `https://api.yourdomain.com/api/v1/auth/google/callback`

## 8. Monitoring

Recommended minimal setup:

- **Uptime**: UptimeRobot or Betterstack monitoring `GET /api/v1/health`
- **Logs**: `docker compose logs -f --tail=100 backend` or forward to Loki/Papertrail
- **DB**: Enable slow query logging in Postgres (`log_min_duration_statement = 500`)
- **Celery**: Flower for task monitoring — add to docker-compose and expose behind auth

```yaml
# Add to docker-compose.prod.yml
flower:
  image: mher/flower
  command: celery --broker=redis://redis:6379/0 flower
  ports:
    - "5555:5555"
  restart: always
```

## 9. Backups

**Postgres:**
```bash
# Dump
docker compose exec postgres pg_dump -U pulse pulse > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T postgres psql -U pulse pulse < backup_20260301.sql
```

Automate with a cron job or use your managed DB provider's automatic backup feature.

**Redis:** Only stores JWT refresh tokens (expire in 7 days) — loss is acceptable if users re-authenticate.

## 10. Checklist

- [ ] All required env vars set (SECRET_KEY, JWT_SECRET_KEY, FERNET_KEY, OPENAI_API_KEY)
- [ ] CORS origins set to actual frontend domain
- [ ] SSL certificates in place
- [ ] Nginx configured with `proxy_buffering off` for SSE
- [ ] Migrations run: `alembic upgrade head`
- [ ] Stripe webhook endpoint registered and secret set
- [ ] Google OAuth redirect URI updated
- [ ] Automatic Postgres backups enabled
- [ ] Uptime monitoring on `/api/v1/health`
- [ ] Celery worker `restart: always` policy set

## Upgrading

1. Pull the latest images:
   ```bash
   docker compose pull
   ```
2. Apply database migrations:
   ```bash
   docker compose up -d
   # Migrations run automatically on backend startup
   # Or manually: make migrate
   ```
3. Verify health:
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

### Breaking Changes
Check the [CHANGELOG](../CHANGELOG.md) before upgrading. Irreversible migrations are noted — always backup first:
```bash
make backup
```

## Troubleshooting

### Redis won't connect
- Check Redis is running: `docker compose ps redis`
- Check Redis health: `docker compose exec redis redis-cli ping`
- Verify `REDIS_HOST` and `REDIS_PORT` in `.env`
- If using external Redis, ensure the host is reachable from the Docker network

### Crawl jobs stuck in "pending"
- Check Celery worker is running: `docker compose ps celery_worker`
- Check worker logs: `docker compose logs celery_worker --tail=50`
- Verify Redis broker is reachable (Celery uses Redis as message broker)
- Restart worker: `docker compose restart celery_worker`

### Out of memory
- Check container memory: `docker stats`
- Reduce Celery concurrency: set `CELERY_WORKER_CONCURRENCY=1` in `.env`
- Reduce DB pool: set `DB_POOL_SIZE=3` and `DB_MAX_OVERFLOW=5` in `.env`
- Consider the light deployment mode (single container)

### Database migration fails
- Check database is running: `docker compose ps postgres`
- Check migration logs: `docker compose logs backend --tail=50`
- Try manual migration: `make migrate`
- For fresh start: `make reset-db` (WARNING: destroys all data)

### Chat responses are slow
- Check LLM API key is valid and has credits
- Check if reranking is enabled (adds latency): disable `use_reranking` on the chatbot
- Monitor worker health: `GET /api/v1/workspaces/{id}/workers/health`
- Consider increasing `CELERY_WORKER_CONCURRENCY`
