# Environment Variables Reference

Complete reference for all Pulse Lite environment variables. See [`.env.example`](../.env.example) for a ready-to-copy template.

## Required

These must be set for the application to start. `make setup` generates secure values automatically.

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `SECRET_KEY` | Application secret for encryption | (required) | `openssl rand -hex 32` |
| `JWT_SECRET_KEY` | JWT signing key | (required) | `openssl rand -hex 32` |
| `FERNET_KEY` | Encryption key for stored API keys (BYOK) | (required) | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ADMIN_EMAIL` | Bootstrap admin account email (auto-created on first startup if no users exist) | `""` | `admin@example.com` |
| `ADMIN_PASSWORD` | Bootstrap admin account password | `""` | `a-strong-password` |

## Database

Connection settings for PostgreSQL. Defaults work with the bundled Docker Compose postgres service.

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_HOST` | PostgreSQL hostname | `localhost` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DB` | Database name | `pulse` |
| `POSTGRES_USER` | Database user | `pulse` |
| `POSTGRES_PASSWORD` | Database password | `pulse_dev_password` |
| `DB_POOL_SIZE` | SQLAlchemy connection pool size | `5` |
| `DB_MAX_OVERFLOW` | Max connections above pool size | `10` |
| `DB_POOL_TIMEOUT` | Seconds to wait for a connection from the pool | `30` |
| `DB_POOL_RECYCLE` | Seconds before a connection is recycled | `1800` |

## Redis

Used for caching, Celery message broker, and Socket.IO adapter. Defaults work with the bundled Docker Compose redis service.

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Redis hostname | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
| `REDIS_PASSWORD` | Redis password (leave empty for no auth) | `""` |

The full Redis URL is constructed automatically as `redis://[:<password>@]<host>:<port>/0`.

## LLM / AI

Pulse Lite uses any OpenAI-compatible API. Set these globally here, or configure per-workspace in **Settings > AI Models**.

Fallback chain: workspace key (Settings > AI Models) -> `AI_API_KEY` env var -> chatbot won't work.

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `AI_BASE_URL` | OpenAI-compatible API base URL | `""` | `https://openrouter.ai/api/v1` |
| `AI_API_KEY` | API key for the AI provider | `""` | `sk-or-v1-...` |
| `DEFAULT_CHATBOT_MODEL` | Model assigned to new chatbots | `""` | `openai/gpt-4o-mini` |
| `INTERNAL_MODEL` | Model for background tasks (autoconfig, analysis, Q&A generation) | `""` | `anthropic/claude-3-haiku` |

### Legacy Provider Keys

Only needed if NOT using the unified `AI_BASE_URL`/`AI_API_KEY` above.

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | `""` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `""` |
| `GOOGLE_AI_API_KEY` | Google AI (Gemini) API key | `""` |
| `OPENROUTER_API_KEY` | OpenRouter API key | `""` |

## Authentication

### JWT

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL in minutes | `30` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL in days | `7` |
| `JWT_SECRET_KEY_PREVIOUS` | Previous JWT key for zero-downtime rotation (see procedure below) | `""` |

**JWT Key Rotation Procedure:**
1. Set `JWT_SECRET_KEY_PREVIOUS` to the current `JWT_SECRET_KEY` value
2. Set `JWT_SECRET_KEY` to the new secret value
3. Restart the application
4. After 30+ minutes (access token TTL), remove `JWT_SECRET_KEY_PREVIOUS`

### Google OAuth (Sign-in with Google)

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | `""` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | `""` |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL | `http://localhost:8000/api/v1/auth/google/callback` |

## Integrations

All integrations are optional. Leave empty to disable.

### Google Drive (Knowledge Base)

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_DRIVE_CLIENT_ID` | Google Drive OAuth client ID | `""` |
| `GOOGLE_DRIVE_CLIENT_SECRET` | Google Drive OAuth client secret | `""` |

### Notion

| Variable | Description | Default |
|----------|-------------|---------|
| `NOTION_CLIENT_ID` | Notion OAuth client ID | `""` |
| `NOTION_CLIENT_SECRET` | Notion OAuth client secret | `""` |
| `NOTION_REDIRECT_URI` | Notion OAuth callback URL | `http://localhost:8000/api/v1/oauth/notion/callback` |

### Slack Bot

| Variable | Description | Default |
|----------|-------------|---------|
| `SLACK_CLIENT_ID` | Slack app client ID | `""` |
| `SLACK_CLIENT_SECRET` | Slack app client secret | `""` |
| `SLACK_SIGNING_SECRET` | Slack request signing secret | `""` |
| `SLACK_BOT_SCOPE` | OAuth scopes for the Slack bot | `app_mentions:read,channels:history,chat:write,im:history,im:write` |

### Meta (WhatsApp / Messenger / Instagram)

| Variable | Description | Default |
|----------|-------------|---------|
| `META_WHATSAPP_VERIFY_TOKEN` | WhatsApp webhook verification token | `""` |
| `META_WHATSAPP_TOKEN` | WhatsApp system token (fallback) | `""` |
| `META_MESSENGER_VERIFY_TOKEN` | Messenger webhook verification token | `""` |
| `META_INSTAGRAM_VERIFY_TOKEN` | Instagram webhook verification token | `""` |

### Shopify

| Variable | Description | Default |
|----------|-------------|---------|
| `SHOPIFY_CLIENT_ID` | Shopify app client ID | `""` |
| `SHOPIFY_CLIENT_SECRET` | Shopify app client secret | `""` |

### Zendesk

| Variable | Description | Default |
|----------|-------------|---------|
| `ZENDESK_CLIENT_ID` | Zendesk OAuth client ID | `""` |
| `ZENDESK_CLIENT_SECRET` | Zendesk OAuth client secret | `""` |

### Dropbox

| Variable | Description | Default |
|----------|-------------|---------|
| `DROPBOX_CLIENT_ID` | Dropbox app key | `""` |
| `DROPBOX_CLIENT_SECRET` | Dropbox app secret | `""` |

### Salesforce

| Variable | Description | Default |
|----------|-------------|---------|
| `SALESFORCE_CLIENT_ID` | Salesforce connected app client ID | `""` |
| `SALESFORCE_CLIENT_SECRET` | Salesforce connected app client secret | `""` |

## Billing (Stripe)

Only relevant when `CLOUD_MODE=true`. Self-hosted deployments can ignore these.

| Variable | Description | Default |
|----------|-------------|---------|
| `STRIPE_SECRET_KEY` | Stripe API secret key | `""` |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret | `""` |

## Deployment

| Variable | Description | Default |
|----------|-------------|---------|
| `CLOUD_MODE` | Enable SaaS features (billing, credits, plan limits) | `false` |
| `serve_frontend` | Serve frontend from backend (light/single-container mode) | `false` |
| `INTERNAL_API_URL` | Internal backend URL used by frontend in light mode | `http://backend:8000` |

## URLs

Adjust these when using a reverse proxy or custom ports.

| Variable | Description | Default |
|----------|-------------|---------|
| `BASE_URL` | Backend public URL (used for OAuth redirect URIs) | `http://localhost:8000` |
| `FRONTEND_URL` | Frontend public URL | `http://localhost:3001` |
| `VITE_API_URL` | API URL used by the frontend SPA | `http://localhost:8000` |
| `VITE_APP_URL` | Frontend URL used by the frontend SPA | `http://localhost:3001` |
| `BACKEND_CORS_ORIGINS` | Explicit CORS origins (JSON array). Auto-derived from `FRONTEND_URL` if not set. | `null` (auto) |

## Performance Tuning

| Variable | Description | Default | Notes |
|----------|-------------|---------|-------|
| `CELERY_WORKER_CONCURRENCY` | Number of Celery worker processes | `2` | Each uses ~250MB RAM. Tasks are I/O-bound, so 2 is enough for most deployments. Increase to 4-8 for many concurrent crawl/ingestion jobs. |
| `DB_POOL_SIZE` | SQLAlchemy connection pool size | `5` | Increase for higher concurrency |
| `DB_MAX_OVERFLOW` | Max connections above pool size | `10` | Reduce if hitting DB connection limits |
| `DB_POOL_TIMEOUT` | Seconds to wait for a pool connection | `30` | Lower to fail fast under load |
| `DB_POOL_RECYCLE` | Seconds before recycling a connection | `1800` | Lower if using managed DB with idle timeouts |
