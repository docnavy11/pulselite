# Pulse

AI-native autonomous resolution platform. The AI resolves support conversations; humans only see what it can't handle. Primary KPI: **Autonomous Resolution Rate**.

## Quick Start

```bash
# 1. Copy env and fill in keys
cp .env.example .env

# 2. Start everything
make up

# 3. Run migrations + seed dev data
make migrate
make seed
```

- Frontend: http://localhost:3001
- Backend API + docs: http://localhost:8000/api/docs
- Dev login: `test@pulse.dev` / `test`

## Makefile Commands

| Command | Description |
|---|---|
| `make up` | Start all containers (postgres, redis, backend, celery, frontend) |
| `make down` | Stop all containers |
| `make build` | Rebuild images |
| `make migrate` | Run Alembic migrations |
| `make migrate-create msg="..."` | Create new migration |
| `make seed` | Seed dev data |
| `make test` | Run backend test suite |
| `make lint` | Lint backend code (ruff) |
| `make logs` | Tail all container logs |
| `make shell-backend` | Bash into backend container |
| `make shell-db` | psql into Postgres |

## Architecture

```
pulse/
├── backend/          FastAPI + SQLAlchemy async + Celery
├── frontend/         Next.js 15 + TypeScript + Tailwind + Zustand
├── widget/           Vanilla TS, Shadow DOM (5.5kb gzipped)
├── docs/             Product blueprint, data model, UX flows
└── infra/            Docker / infrastructure config
```

**Ports (Docker)**
| Service | External | Internal |
|---|---|---|
| Frontend | 3001 | 3000 |
| Backend | 8000 | 8000 |
| Postgres | 5432 | 5432 |
| Redis | 6379 | 6379 |

## Key Concepts

| Concept | Description |
|---|---|
| **Workspace** | Tenant unit — all data is workspace-scoped |
| **Chatbot** | An AI agent with its own KB, persona, and widget |
| **Exceptions Queue** | The ~10% of conversations the AI escalates to humans |
| **Gap Cluster** | A group of unanswered questions → auto-drafts KB article |
| **Resolution Rate** | % of conversations resolved by AI without human touch |

## Environment Variables

See `.env.example` for full list. Required to set:
- `SECRET_KEY` + `JWT_SECRET_KEY` — any long random strings
- `OPENAI_API_KEY` — for embeddings and default LLM
- `FERNET_KEY` — for BYOK key encryption (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)

Optional (features degrade gracefully without them):
- `GOOGLE_CLIENT_ID/SECRET` — Google OAuth
- `ANTHROPIC_API_KEY` / `GOOGLE_AI_API_KEY` — alternative LLM providers
- `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` — billing

## Docs

| File | Contents |
|---|---|
| `docs/gaps.md` | Full feature gap list — spec gaps + Chatbase parity gaps, prioritized |
| `docs/api_reference.md` | All 22 API routers — endpoints, params, response shapes |
| `docs/deployment.md` | Production deployment guide (Nginx, Stripe, scaling, backups) |
| `docs/PRODUCT_BLUEPRINT.md` | Vision, positioning, full feature spec |
| `docs/pulse_dev_handover.md` | NFRs, module specs, engineering handover |
| `docs/pulse_data_model.md` | 32-table SQL schema |
| `docs/pulse_ux_flows.md` | Screen-by-screen UX for novel features |
| `docs/intelligence_layer_research.md` | Research behind the intelligence modules |
| `docs/rag_chunking_research.md` | RAG pipeline design decisions |
| `docs/chatbase_full_feature_list.md` | Competitive research — Chatbase feature inventory |
| `CHANGELOG.md` | What was built and when |
