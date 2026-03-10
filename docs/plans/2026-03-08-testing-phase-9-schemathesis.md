# Phase 9 — API Fuzz Testing (Schemathesis) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run Schemathesis against the Pulse OpenAPI spec to auto-generate and fire edge-case test cases at all API endpoints, catching unhandled 5xx errors, missing validation, and type coercion bugs.

**Architecture:** Schemathesis is installed on the host and runs against the live Docker-hosted backend (`http://localhost:8000`). Two passes: (1) unauthenticated endpoints with no token, (2) authenticated endpoints with a real JWT obtained via login. SSE streaming endpoints and OAuth redirect endpoints are excluded (they require interactive flows). Results gate on any `5xx` response or schema validation failure. A `make test-schema` target ties it all together.

**Tech Stack:** Schemathesis 3.x (pip), pytest-schemathesis, FastAPI OpenAPI 3.1.0 spec at `http://localhost:8000/openapi.json`

---

## Context

- OpenAPI spec: `http://localhost:8000/openapi.json` (114 paths, FastAPI default)
- Dev credentials: `test@pulse.dev` / `test`
- Dev workspace ID: `350863e7-3dc8-430e-bc23-fd41d4499d7b`
- Dev chatbot ID: `a8dfa0e8-b077-4bcc-9d2a-00bdf3e4f108`
- Backend in Docker at `http://localhost:8000`
- **Endpoints to EXCLUDE** (require interactive/streaming flows):
  - `/api/v1/chat` and `/api/v1/chat/completions` — SSE streaming, incompatible with schemathesis
  - `/api/v1/public/chat` and `/api/v1/public/chat/lead` — rate-limited (3/min) + SSE
  - All `/auth/google*`, `/auth/sso*`, `/oauth/*`, `/shopify*` — OAuth redirect flows
  - All Meta webhook endpoints (`/whatsapp/*`, `/messenger/*`, `/instagram/*`, `/slack-events/*`)

---

### Task 1: Install Schemathesis, run against unauthenticated endpoints

**Files:**
- Create: `backend/schemathesis.toml` (exclusion config)
- Modify: `Makefile`

**Step 1: Install schemathesis on the host**

```bash
pip install schemathesis
st --version
```

Expected: prints `schemathesis, version 3.x.x`

If `pip` not available: `pip3 install schemathesis` or `pipx install schemathesis`.

**Step 2: Verify the OpenAPI spec is accessible**

```bash
docker compose exec backend python -c "
from app.main import app
import json
spec = app.openapi()
print('openapi:', spec['openapi'])
print('paths:', len(spec['paths']))
"
```

The spec is served at `http://localhost:8000/openapi.json` when the container is up.

**Step 3: Run schemathesis against public (no-auth) endpoints only**

Exclude authenticated and problematic paths using `--exclude-path-regex`:

```bash
st run http://localhost:8000/openapi.json \
  --checks all \
  --exclude-path-regex "/auth/google|/auth/sso|/oauth|/shopify|/whatsapp|/messenger|/instagram|/slack" \
  --exclude-path-regex "/public/chat|/share/" \
  --hypothesis-max-examples=10 \
  --validate-schema=false \
  2>&1
```

`--hypothesis-max-examples=10` keeps it fast (10 generated cases per endpoint).
`--validate-schema=false` suppresses OpenAPI 3.1 vs 3.0 schema warnings.

Read ALL output. Note any `5xx` responses or `ERROR` results — these are genuine bugs.

**Step 4: Fix any 5xx findings**

For each endpoint returning 5xx under schemathesis:
- Identify the route handler in `backend/app/api/v1/`
- Find the missing input validation (usually Pydantic schema missing a field constraint)
- Add the constraint (e.g. `gt=0`, `min_length=1`, `Pattern(r"...")`)
- Common fix: adding `Optional[str] = None` to fields that are missing but expected

**Step 5: Create `backend/schemathesis.toml`**

```toml
[tool.schemathesis]
checks = ["all"]
hypothesis_max_examples = 10
validate_schema = false
```

**Step 6: Add `test-schema-public` target to Makefile**

```makefile
test-schema-public:
	st run http://localhost:8000/openapi.json \
	  --checks all \
	  --exclude-path-regex "/auth/google|/auth/sso|/oauth|/shopify|/whatsapp|/messenger|/instagram|/slack" \
	  --exclude-path-regex "/public/chat|/share/" \
	  --hypothesis-max-examples=10 \
	  --validate-schema=false
```

IMPORTANT: Makefile uses TAB indentation. Multi-line shell commands use `\` at end of each line.

Add `test-schema-public` to the `.PHONY` line.

**Step 7: Verify `make test-schema-public` exits 0**

```bash
make test-schema-public
```

**Step 8: Commit**

```bash
git add backend/schemathesis.toml Makefile
git add backend/app/  # any fixed files
git commit -m "test: add schemathesis public endpoint fuzz testing"
```

---

### Task 2: Authenticated schemathesis + `make test-schema` gate

**Files:**
- Create: `backend/tests/test_schema_auth.py`
- Modify: `Makefile`

**Step 1: Obtain a real JWT token for schemathesis**

```bash
TOKEN=$(docker compose exec backend python -c "
from app.utils.security import create_access_token
token = create_access_token({'sub': 'c31b8c52-0de7-4a2f-a7a8-d9a8e26a9b11', 'type': 'access'})
print(token)
")
echo $TOKEN
```

Wait — the `sub` must be a real agent UUID. Get it from the seeded agent:

```bash
docker compose exec backend python -c "
import asyncio
from app.database import async_session_factory
from app.models.organizational import Agent
from sqlalchemy import select

async def get_agent():
    async with async_session_factory() as db:
        result = await db.execute(select(Agent).limit(1))
        agent = result.scalar_one()
        print(str(agent.id))

asyncio.run(get_agent())
"
```

OR simply login via the API:

```bash
TOKEN=$(docker compose exec backend python -c "
import httpx
import asyncio

async def login():
    async with httpx.AsyncClient(base_url='http://localhost:8000') as client:
        r = await client.post('/api/v1/auth/login', json={'email': 'test@pulse.dev', 'password': 'test'})
        data = r.json()
        print(data['tokens']['access_token'])

asyncio.run(login())
")
echo "Token obtained: ${TOKEN:0:20}..."
```

Actually the simplest approach — use `curl` from within the container:

```bash
TOKEN=$(docker compose exec backend bash -c "python -c \"
import httpx, asyncio
async def get():
    async with httpx.AsyncClient() as c:
        r = await c.post('http://localhost:8000/api/v1/auth/login', json={'email':'test@pulse.dev','password':'test'})
        print(r.json()['tokens']['access_token'])
asyncio.run(get())
\"")
echo $TOKEN | head -c 40
```

**Step 2: Run schemathesis with auth token against all workspace paths**

```bash
st run http://localhost:8000/openapi.json \
  --checks all \
  --auth-type bearer \
  --auth "$TOKEN" \
  --exclude-path-regex "/auth/google|/auth/sso|/oauth|/shopify|/whatsapp|/messenger|/instagram|/slack" \
  --exclude-path-regex "/public/chat|/share/|/chat$|/chat/completions" \
  --hypothesis-max-examples=10 \
  --validate-schema=false \
  --header "X-Workspace-Id: 350863e7-3dc8-430e-bc23-fd41d4499d7b" \
  2>&1
```

Note: many workspace-scoped paths use `{workspace_id}` as a path parameter — schemathesis will generate random UUIDs which will return 403/404 (not 5xx). Only 5xx responses are failures.

**Step 3: Fix any 5xx findings from the authenticated run**

Same approach as Task 1 Step 4.

**Step 4: Add `test-schema-auth` and `test-schema` Makefile targets**

The auth target must obtain the token dynamically. The cleanest approach: a shell one-liner inside the Makefile.

```makefile
test-schema-auth:
	@TOKEN=$$(docker compose exec -T backend python -c "\
import httpx, asyncio; \
async def g(): \
    async with httpx.AsyncClient() as c: \
        r = await c.post('http://localhost:8000/api/v1/auth/login', json={'email':'test@pulse.dev','password':'test'}); \
        print(r.json()['tokens']['access_token']); \
asyncio.run(g())") && \
	st run http://localhost:8000/openapi.json \
	  --checks all \
	  --auth-type bearer \
	  --auth "$$TOKEN" \
	  --exclude-path-regex "/auth/google|/auth/sso|/oauth|/shopify|/whatsapp|/messenger|/instagram|/slack" \
	  --exclude-path-regex "/public/chat|/share/|/chat$$|/chat/completions" \
	  --hypothesis-max-examples=10 \
	  --validate-schema=false

test-schema: test-schema-public test-schema-auth
```

Add `test-schema-auth test-schema` to `.PHONY`.

**Step 5: Verify `make test-schema` exits 0**

```bash
make test-schema
```

Expected: both runs complete, exit 0, no 5xx responses.

**Step 6: Commit**

```bash
git add Makefile
git add backend/app/  # any fixed files
git commit -m "test: add schemathesis authenticated endpoint fuzz testing + test-schema gate"
```

**Step 7: Print summary**

After committing:
```
Phase 9 complete.
Schemathesis: X endpoints tested (public), Y endpoints tested (auth)
5xx findings: N fixed
Gate: make test-schema exits 0
```
