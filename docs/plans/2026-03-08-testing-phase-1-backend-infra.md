# Testing Phase 1 — Backend Test Infrastructure

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Set up the complete backend test infrastructure — pytest config, async DB fixtures, model factories, auth helpers — so every subsequent test phase can build on a shared, reliable foundation.

**Architecture:** Tests use a dedicated `pulse_test` Postgres database. Each test gets an async SQLAlchemy session that wraps all writes in a transaction that is rolled back after the test, so tests are isolated without recreating the schema. The FastAPI app's `get_db` dependency is overridden to inject the test session. Auth dependencies (`get_current_user`, `get_workspace`) are overrideable per-test or use a seeded agent by default.

**Tech Stack:** pytest 8.3+, pytest-asyncio (auto mode), pytest-mock, httpx AsyncClient, faker, SQLAlchemy 2.0 async, asyncpg, real Postgres (pulse_test DB), real Redis

---

## Before You Start — Verify Prerequisites

These must be true before implementing anything:

```bash
# 1. Docker stack is running
make up
docker compose ps  # postgres, redis, backend must be Up

# 2. Test DB doesn't already exist (or it's OK to use existing)
docker compose exec postgres psql -U pulse -c "\l" | grep pulse_test

# 3. Existing tests still pass
docker compose exec backend pytest backend/tests/ -v
# Expected: 12 passed (csv + sitemap tests)

# 4. Python dev deps are installed inside container
docker compose exec backend pip list | grep pytest
# Expected: pytest, pytest-asyncio shown
```

---

## Task 1: Add test dependencies to pyproject.toml

**Files:**
- Modify: `backend/pyproject.toml`

**What to test before building:**
- Run `docker compose exec backend pip list | grep -E "pytest|faker|mock"` to see what's already installed.

**Step 1: Read the current pyproject.toml dev section**

```bash
grep -A 20 "optional-dependencies" backend/pyproject.toml
```

**Step 2: Add missing test dependencies**

In `backend/pyproject.toml`, find the `[project.optional-dependencies]` section. Add or extend the `dev` group to include:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "pytest-mock>=3.14.0",
    "pytest-xdist>=3.6.0",
    "faker>=33.0.0",
    "ruff>=0.8.0",
    "anyio[trio]>=4.0.0",
]
```

Note: `httpx` is already in main dependencies, no need to add it.

**Step 3: Install inside the backend container**

```bash
docker compose exec backend pip install -e ".[dev]"
```

**Step 4: Verify**

```bash
docker compose exec backend pip list | grep -E "pytest-cov|pytest-mock|faker|pytest-xdist"
```
Expected output shows all 4 packages with version numbers.

**Step 5: Update Makefile with new test targets**

In `Makefile`, find the existing `test:` target and add below it:

```makefile
test-unit:
	docker compose exec backend pytest backend/tests/unit/ -v

test-integration:
	docker compose exec backend pytest backend/tests/integration/ -v

test-isolation:
	docker compose exec backend pytest backend/tests/integration/test_tenant_isolation.py -v

test-security:
	docker compose exec backend pytest backend/tests/security/ -v

test-all:
	docker compose exec backend pytest backend/tests/ --cov=app --cov-report=html --cov-fail-under=80

test-fast:
	docker compose exec backend pytest backend/tests/unit/ -n auto
```

**Step 6: Verify Makefile**

```bash
make test-unit
```
Expected: `no tests ran` (no unit tests exist yet) — that's fine, no error.

**Step 7: Commit**

```bash
git add backend/pyproject.toml Makefile
git commit -m "test: add pytest-cov, pytest-mock, faker, pytest-xdist; add Makefile test targets"
```

---

## Task 2: Create the test database

**Files:**
- Create: `backend/tests/.env.test`

**What to test before building:**
- Verify Postgres is accessible: `docker compose exec postgres psql -U pulse -c "SELECT 1;"`

**Step 1: Create the test database**

```bash
docker compose exec postgres createdb -U pulse pulse_test
```

Expected: no output (success). If it says "already exists", that's also fine.

**Step 2: Run Alembic migrations on the test database**

```bash
docker compose exec backend bash -c "DATABASE_URL='postgresql+asyncpg://pulse:pulse_dev_password@postgres:5432/pulse_test' alembic upgrade head"
```

Expected: Alembic prints migration steps. Last line: `INFO  [alembic.runtime.migration] Running upgrade ... -> ...`

**Step 3: Create the test environment file**

Create `backend/tests/.env.test`:

```bash
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=pulse_test
POSTGRES_USER=pulse
POSTGRES_PASSWORD=pulse_dev_password
REDIS_HOST=redis
REDIS_PORT=6379
JWT_SECRET_KEY=test-secret-key-at-least-32-chars-long
SECRET_KEY=test-secret-key-at-least-32-chars-long
```

For `FERNET_KEY`, generate one:
```bash
docker compose exec backend python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Copy the output and add to `.env.test`:
```
FERNET_KEY=<paste here>
```

Also add dummy values for external services (tests will mock these):
```
OPENAI_API_KEY=sk-test-not-real
ANTHROPIC_API_KEY=test-not-real
STRIPE_SECRET_KEY=sk_test_not_real
STRIPE_WEBHOOK_SECRET=whsec_test_not_real
GOOGLE_CLIENT_ID=test-client-id
GOOGLE_CLIENT_SECRET=test-client-secret
```

**Step 4: Add .env.test to .gitignore if not already there**

```bash
grep ".env.test" backend/.gitignore || echo "tests/.env.test" >> backend/.gitignore
```

**Step 5: Verify test DB has tables**

```bash
docker compose exec postgres psql -U pulse pulse_test -c "\dt" | head -20
```
Expected: List of tables (workspaces, agents, conversations, etc.)

**Step 6: Commit**

```bash
git add backend/pyproject.toml  # if not already committed
git commit -m "test: create pulse_test database and run migrations"
```

---

## Task 3: Create conftest.py — async DB fixtures

**Files:**
- Create: `backend/tests/conftest.py`

**What to test before building:**
- Understand how `get_db` works: `cat backend/app/database.py`
- Understand how `create_app` works: `grep -n "create_app\|app = " backend/app/main.py`

**Step 1: Write the failing test first**

Create `backend/tests/test_conftest_smoke.py`:

```python
"""Smoke tests to verify conftest fixtures work."""
import pytest


async def test_db_session_exists(db):
    """db fixture provides an async session."""
    from sqlalchemy.ext.asyncio import AsyncSession
    assert isinstance(db, AsyncSession)


async def test_client_can_reach_health(client):
    """client fixture can hit the health endpoint."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
```

**Step 2: Run — expect it to FAIL (no conftest.py yet)**

```bash
docker compose exec backend pytest backend/tests/test_conftest_smoke.py -v
```
Expected: `ERROR` — `fixture 'db' not found` and `fixture 'client' not found`

**Step 3: Create `backend/tests/conftest.py`**

```python
"""
Global pytest fixtures for the Pulse test suite.

Architecture:
  - 'engine': one per session, connects to pulse_test DB
  - 'db': one per test, wraps all writes in a SAVEPOINT that rolls back
  - 'app': FastAPI app with get_db overridden to use the test session
  - 'client': httpx AsyncClient connected to the test app
  - 'workspace', 'agent', 'auth_client': pre-seeded entities
"""
import os
import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator

import httpx
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)

# Point at the test database — override env before importing app modules
os.environ.setdefault("POSTGRES_DB", "pulse_test")
os.environ.setdefault("POSTGRES_HOST", "postgres")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_USER", "pulse")
os.environ.setdefault("POSTGRES_PASSWORD", "pulse_dev_password")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-at-least-32-chars-long")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-chars-long")

# Import app AFTER env is set
from app.main import create_app
from app.database import get_db
from app.models.base import Base


# ── Engine (session-scoped: create once per test run) ────────────────────────

@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    db_url = (
        f"postgresql+asyncpg://"
        f"{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}"
        f"/{os.environ['POSTGRES_DB']}"
    )
    eng = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    yield eng
    await eng.dispose()


# ── DB session (function-scoped: each test gets a rolled-back transaction) ───

@pytest_asyncio.fixture
async def db(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a per-test async session that rolls back after the test.
    Uses a nested SAVEPOINT so the outer transaction is never committed.
    """
    connection = await engine.connect()
    transaction = await connection.begin()

    session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = session_factory()

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


# ── FastAPI app with dependency overrides ────────────────────────────────────

@pytest_asyncio.fixture
async def app(db: AsyncSession):
    """FastAPI app with get_db overridden to use the test session."""
    application = create_app()

    async def override_get_db():
        yield db

    application.dependency_overrides[get_db] = override_get_db
    yield application
    application.dependency_overrides.clear()


# ── HTTP client ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client connected to the test app."""
    async with httpx.AsyncClient(
        app=app,
        base_url="http://testserver",
    ) as c:
        yield c


# ── Seeded workspace + agent ──────────────────────────────────────────────────

@pytest_asyncio.fixture
async def workspace(db: AsyncSession):
    """A pre-created test workspace."""
    from app.models.organizational import Workspace
    import uuid

    ws = Workspace(
        id=uuid.uuid4(),
        name="Test Workspace",
        slug=f"test-ws-{uuid.uuid4().hex[:8]}",
        plan="pro",
    )
    db.add(ws)
    await db.flush()
    return ws


@pytest_asyncio.fixture
async def agent(db: AsyncSession, workspace):
    """A pre-created agent with owner membership in the test workspace."""
    from app.models.organizational import Agent, WorkspaceMembership
    from app.utils.security import hash_password
    import uuid

    ag = Agent(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4().hex[:8]}@pulse.test",
        name="Test Agent",
        password_hash=hash_password("testpassword123"),
        workspace_id=workspace.id,
    )
    db.add(ag)
    await db.flush()

    membership = WorkspaceMembership(
        agent_id=ag.id,
        workspace_id=workspace.id,
        role="owner",
    )
    db.add(membership)
    await db.flush()
    return ag


@pytest_asyncio.fixture
async def auth_headers(agent):
    """Authorization headers with a valid JWT for the test agent."""
    from app.utils.security import create_access_token

    token = create_access_token({"sub": str(agent.id), "type": "access"})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_client(client, agent, workspace):
    """
    httpx client pre-configured with auth headers.
    Provides .workspace_id and .agent_id as attributes for convenience.
    """
    from app.utils.security import create_access_token

    token = create_access_token({"sub": str(agent.id), "type": "access"})
    client.headers.update({"Authorization": f"Bearer {token}"})
    client.workspace_id = str(workspace.id)
    client.agent_id = str(agent.id)
    return client
```

**Step 4: Check what `hash_password` and `create_access_token` are actually called**

```bash
grep -n "def hash_password\|def create_access_token\|def encode_token" backend/app/utils/security.py
```

Adjust the import in conftest.py if the function names differ.

**Step 5: Run the smoke tests — expect them to PASS**

```bash
docker compose exec backend pytest backend/tests/test_conftest_smoke.py -v
```
Expected:
```
PASSED tests/test_conftest_smoke.py::test_db_session_exists
PASSED tests/test_conftest_smoke.py::test_client_can_reach_health
```

If any fail, read the error carefully. Common issues:
- `FERNET_KEY` not set → add to env overrides at top of conftest.py
- `asyncio_mode = "auto"` not in pyproject.toml → verify it's there
- Import error → check the exact function name in `security.py`

**Step 6: Commit**

```bash
git add backend/tests/conftest.py backend/tests/test_conftest_smoke.py
git commit -m "test: add conftest.py with async DB session, app, and auth fixtures"
```

---

## Task 4: Create model factories

**Files:**
- Create: `backend/tests/factories/__init__.py`
- Create: `backend/tests/factories/workspace.py`
- Create: `backend/tests/factories/chatbot.py`
- Create: `backend/tests/factories/conversation.py`

**What to test before building:**
- Verify model field names: `grep -n "class Chatbot\|workspace_id\|name\|llm_provider" backend/app/models/knowledge.py | head -20`

**Step 1: Create `backend/tests/factories/__init__.py`**

```python
"""Factory helpers for creating test data in the pulse_test database."""
from .workspace import make_workspace, make_agent, make_membership
from .chatbot import make_chatbot, make_knowledge_base, make_document
from .conversation import make_conversation, make_message

__all__ = [
    "make_workspace", "make_agent", "make_membership",
    "make_chatbot", "make_knowledge_base", "make_document",
    "make_conversation", "make_message",
]
```

**Step 2: Create `backend/tests/factories/workspace.py`**

```python
"""Factories for workspace, agent, and membership models."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organizational import Workspace, Agent, WorkspaceMembership
from app.utils.security import hash_password


async def make_workspace(
    db: AsyncSession,
    *,
    name: str = "Test Workspace",
    plan: str = "pro",
    slug: str | None = None,
) -> Workspace:
    ws = Workspace(
        id=uuid.uuid4(),
        name=name,
        slug=slug or f"ws-{uuid.uuid4().hex[:8]}",
        plan=plan,
    )
    db.add(ws)
    await db.flush()
    return ws


async def make_agent(
    db: AsyncSession,
    workspace: Workspace,
    *,
    email: str | None = None,
    name: str = "Test User",
    password: str = "testpassword123",
    role: str = "member",
) -> tuple[Agent, WorkspaceMembership]:
    """Create an agent AND their workspace membership. Returns (agent, membership)."""
    agent = Agent(
        id=uuid.uuid4(),
        email=email or f"user-{uuid.uuid4().hex[:8]}@pulse.test",
        name=name,
        password_hash=hash_password(password),
        workspace_id=workspace.id,
    )
    db.add(agent)
    await db.flush()

    membership = await make_membership(db, agent=agent, workspace=workspace, role=role)
    return agent, membership


async def make_membership(
    db: AsyncSession,
    *,
    agent: Agent,
    workspace: Workspace,
    role: str = "member",
) -> WorkspaceMembership:
    m = WorkspaceMembership(
        agent_id=agent.id,
        workspace_id=workspace.id,
        role=role,
    )
    db.add(m)
    await db.flush()
    return m
```

**Step 3: Create `backend/tests/factories/chatbot.py`**

```python
"""Factories for chatbot, knowledge base, and document models."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organizational import Workspace
from app.models.knowledge import Chatbot, KnowledgeBase, Document


async def make_chatbot(
    db: AsyncSession,
    workspace: Workspace,
    *,
    name: str = "Test Bot",
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini",
    confidence_threshold: float = 0.7,
) -> Chatbot:
    bot = Chatbot(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        name=name,
        display_name=name,
        system_prompt="You are a helpful assistant.",
        llm_provider=llm_provider,
        llm_model=llm_model,
        confidence_threshold=confidence_threshold,
        retrieval_top_k=5,
        use_reranking=False,
        use_hybrid_retrieval=True,
        widget_config={},
    )
    db.add(bot)
    await db.flush()
    return bot


async def make_knowledge_base(
    db: AsyncSession,
    workspace: Workspace,
    chatbot: Chatbot,
    *,
    name: str = "Test KB",
) -> KnowledgeBase:
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        chatbot_id=chatbot.id,
        name=name,
        kb_type="general",
    )
    db.add(kb)
    await db.flush()
    return kb


async def make_document(
    db: AsyncSession,
    workspace: Workspace,
    knowledge_base: KnowledgeBase,
    *,
    title: str = "Test Document",
    source_type: str = "text",
    content: str = "This is test content for the document.",
    status: str = "indexed",
) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        knowledge_base_id=knowledge_base.id,
        title=title,
        source_type=source_type,
        content=content,
        status=status,
        chunk_count=1,
    )
    db.add(doc)
    await db.flush()
    return doc
```

**Step 4: Create `backend/tests/factories/conversation.py`**

```python
"""Factories for conversation and message models."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organizational import Workspace
from app.models.knowledge import Chatbot
from app.models.conversations import Conversation, Message


async def make_conversation(
    db: AsyncSession,
    workspace: Workspace,
    chatbot: Chatbot,
    *,
    status: str = "open",
    autonomous_resolved: bool = False,
    escalation_reason: str | None = None,
    confidence_avg: float | None = None,
) -> Conversation:
    conv = Conversation(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        chatbot_id=chatbot.id,
        status=status,
        autonomous_resolved=autonomous_resolved,
        escalation_reason=escalation_reason,
        confidence_avg=confidence_avg,
        channel="widget",
    )
    db.add(conv)
    await db.flush()
    return conv


async def make_message(
    db: AsyncSession,
    conversation: Conversation,
    workspace: Workspace,
    *,
    content: str = "Hello, I need help.",
    author_type: str = "user",
    confidence_score: float | None = None,
) -> Message:
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        workspace_id=workspace.id,
        content=content,
        author_type=author_type,
        message_type="text",
        confidence_score=confidence_score,
    )
    db.add(msg)
    await db.flush()
    return msg
```

**Step 5: Write a test to verify factories work**

Create `backend/tests/test_factories_smoke.py`:

```python
"""Verify factory functions create valid DB records."""
import pytest
from tests.factories import (
    make_workspace, make_agent, make_chatbot,
    make_knowledge_base, make_conversation, make_message,
)


async def test_make_workspace_creates_record(db):
    ws = await make_workspace(db, name="Factory Test WS")
    assert ws.id is not None
    assert ws.name == "Factory Test WS"
    assert ws.slug.startswith("ws-")


async def test_make_agent_creates_agent_and_membership(db):
    ws = await make_workspace(db)
    agent, membership = await make_agent(db, ws, role="admin")
    assert agent.email.endswith("@pulse.test")
    assert membership.role == "admin"
    assert membership.workspace_id == ws.id
    assert membership.agent_id == agent.id


async def test_make_chatbot_creates_record(db):
    ws = await make_workspace(db)
    bot = await make_chatbot(db, ws)
    assert bot.workspace_id == ws.id
    assert bot.llm_provider == "openai"


async def test_make_conversation_and_messages(db):
    ws = await make_workspace(db)
    bot = await make_chatbot(db, ws)
    conv = await make_conversation(db, ws, bot)
    msg = await make_message(db, conv, ws, content="Test message")

    assert conv.workspace_id == ws.id
    assert msg.conversation_id == conv.id
    assert msg.content == "Test message"


async def test_two_workspaces_are_isolated(db):
    ws_a = await make_workspace(db, name="Workspace A")
    ws_b = await make_workspace(db, name="Workspace B")
    bot_a = await make_chatbot(db, ws_a, name="Bot A")
    bot_b = await make_chatbot(db, ws_b, name="Bot B")

    assert bot_a.workspace_id == ws_a.id
    assert bot_b.workspace_id == ws_b.id
    assert bot_a.workspace_id != bot_b.workspace_id
```

**Step 6: Run the factory tests**

```bash
docker compose exec backend pytest backend/tests/test_factories_smoke.py -v
```
Expected: 5 tests pass. If any fail, check the exact field names in the model against what the factory sets.

**Step 7: Delete the smoke test files (they're now verified, move to permanent)**

```bash
# Keep the factories, remove temporary smoke files
rm backend/tests/test_conftest_smoke.py backend/tests/test_factories_smoke.py
```

We'll write proper tests in Phase 2+. These were just to verify the infra.

**Step 8: Commit**

```bash
git add backend/tests/
git commit -m "test: add model factories for workspace, chatbot, conversation"
```

---

## Task 5: Create `backend/tests/unit/` and `backend/tests/integration/` directories

**Files:**
- Create: `backend/tests/unit/__init__.py`
- Create: `backend/tests/integration/__init__.py`
- Create: `backend/tests/security/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p backend/tests/unit
mkdir -p backend/tests/integration
mkdir -p backend/tests/security
touch backend/tests/unit/__init__.py
touch backend/tests/integration/__init__.py
touch backend/tests/security/__init__.py
```

**Step 2: Add a placeholder test in each to verify pytest discovers them**

`backend/tests/unit/__init__.py` — empty file

`backend/tests/integration/__init__.py` — empty file

`backend/tests/security/__init__.py` — empty file

**Step 3: Verify pytest discovers all test directories**

```bash
docker compose exec backend pytest backend/tests/ --collect-only 2>&1 | head -20
```
Expected: sees `tests/unit`, `tests/integration`, `tests/security` as collection paths. Shows the existing csv/sitemap tests.

**Step 4: Update pytest config to set testpaths**

In `backend/pyproject.toml`, update `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
```

**Step 5: Verify**

```bash
docker compose exec backend pytest --collect-only 2>&1 | tail -5
```
Expected: `12 tests collected` (the existing csv + sitemap tests).

**Step 6: Commit**

```bash
git add backend/tests/ backend/pyproject.toml
git commit -m "test: create unit/, integration/, security/ test directories; configure pytest testpaths"
```

---

## Task 6: Add auth helper — `auth_headers` fixture for two-workspace scenarios

**Files:**
- Modify: `backend/tests/conftest.py`

The tenant isolation tests need to create **two** separate workspaces with different agents and get auth headers for each. Add a factory-based auth helper.

**Step 1: Add `make_auth_headers` helper to conftest.py**

Append to `backend/tests/conftest.py`:

```python
# ── Auth headers factory (for multi-workspace isolation tests) ────────────────

async def make_auth_headers_for(agent: "Agent") -> dict[str, str]:
    """
    Generate a valid JWT Authorization header for any agent.
    Use this in isolation tests where you need multiple agents.
    """
    from app.utils.security import create_access_token
    token = create_access_token({"sub": str(agent.id), "type": "access"})
    return {"Authorization": f"Bearer {token}"}
```

Also add a `second_workspace` fixture and `second_agent` fixture that tenants isolation tests can use:

```python
@pytest_asyncio.fixture
async def second_workspace(db: AsyncSession):
    """A second workspace, completely separate from the first."""
    from app.models.organizational import Workspace
    import uuid
    ws = Workspace(
        id=uuid.uuid4(),
        name="Second Workspace",
        slug=f"second-ws-{uuid.uuid4().hex[:8]}",
        plan="pro",
    )
    db.add(ws)
    await db.flush()
    return ws


@pytest_asyncio.fixture
async def second_agent(db: AsyncSession, second_workspace):
    """An agent with owner membership in the second workspace."""
    from app.models.organizational import Agent, WorkspaceMembership
    from app.utils.security import hash_password
    import uuid

    ag = Agent(
        id=uuid.uuid4(),
        email=f"second-{uuid.uuid4().hex[:8]}@pulse.test",
        name="Second Agent",
        password_hash=hash_password("testpassword123"),
        workspace_id=second_workspace.id,
    )
    db.add(ag)
    await db.flush()

    m = WorkspaceMembership(
        agent_id=ag.id,
        workspace_id=second_workspace.id,
        role="owner",
    )
    db.add(m)
    await db.flush()
    return ag
```

**Step 2: Write a test to verify multi-workspace auth headers work**

```python
# backend/tests/integration/test_auth_headers_smoke.py
async def test_two_agents_get_different_tokens(db, agent, second_agent):
    """Verify two agents get distinct JWTs."""
    from tests.conftest import make_auth_headers_for
    headers_a = await make_auth_headers_for(agent)
    headers_b = await make_auth_headers_for(second_agent)
    assert headers_a["Authorization"] != headers_b["Authorization"]
```

**Step 3: Run**

```bash
docker compose exec backend pytest backend/tests/integration/test_auth_headers_smoke.py -v
```
Expected: 1 test passes.

**Step 4: Remove smoke test**

```bash
rm backend/tests/integration/test_auth_headers_smoke.py
```

**Step 5: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: add second_workspace/second_agent fixtures and make_auth_headers_for helper"
```

---

## Task 7: Verify full infrastructure with one real integration test

Before declaring Phase 1 done, write ONE real integration test that exercises the full stack: HTTP request → dependency override → real DB query → response.

**Files:**
- Create: `backend/tests/integration/test_health.py`

**Step 1: Write the test**

```python
"""
Smoke integration test verifying the full test stack works:
real DB connection, dependency override, HTTP client.
"""


async def test_health_endpoint_returns_200(client):
    """The /health endpoint should always return 200 with DB connected."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"


async def test_authenticated_endpoint_requires_auth(client):
    """Endpoints without auth header should return 401 or 403."""
    response = await client.get("/api/v1/workspaces")
    assert response.status_code in (401, 403)


async def test_authenticated_endpoint_works_with_auth(auth_client, workspace):
    """An authenticated client can list workspaces and see their own workspace."""
    response = await auth_client.get("/api/v1/workspaces")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    workspace_ids = [ws["id"] for ws in data]
    assert str(workspace.id) in workspace_ids


async def test_db_rollback_isolation(db, auth_client, workspace):
    """Data created in this test should not persist after the test."""
    from tests.factories import make_chatbot
    bot = await make_chatbot(db, workspace, name="Rollback Test Bot")
    # Verify it exists in this test's session
    assert bot.id is not None
    # The rollback happens automatically in the db fixture teardown
    # After this test, the bot row is gone — subsequent tests won't see it
```

**Step 2: Run all integration tests**

```bash
docker compose exec backend pytest backend/tests/integration/ -v
```
Expected: 4 tests pass.

**Step 3: Run the full test suite**

```bash
docker compose exec backend pytest backend/tests/ -v
```
Expected: existing 12 tests + 4 new = 16 tests pass.

**Step 4: Commit**

```bash
git add backend/tests/integration/test_health.py
git commit -m "test: add health + auth smoke integration tests — Phase 1 complete"
```

---

## Phase 1 Completion Checklist

Before moving to Phase 2, verify all of the following:

```bash
# 1. New test dependencies installed
docker compose exec backend pip show pytest-cov pytest-mock faker pytest-xdist

# 2. Test database exists and has all tables
docker compose exec postgres psql -U pulse pulse_test -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"
# Expected: count > 30

# 3. All Makefile targets work
make test-unit     # no tests yet, exits 0
make test-integration  # 4 tests pass
make test          # all tests pass

# 4. Full suite passes
docker compose exec backend pytest backend/tests/ -v
# Expected: all tests pass

# 5. Coverage tool works
docker compose exec backend pytest backend/tests/ --cov=app --cov-report=term-missing 2>&1 | tail -5
```

### What Phase 1 Delivers

| Deliverable | Location |
|---|---|
| Test DB (`pulse_test`) | Docker postgres service |
| pytest config | `backend/pyproject.toml` |
| Async DB session fixture | `backend/tests/conftest.py` |
| FastAPI test app fixture | `backend/tests/conftest.py` |
| Auth header fixtures | `backend/tests/conftest.py` |
| Model factories | `backend/tests/factories/` |
| Test directory structure | `backend/tests/unit/`, `integration/`, `security/` |
| Makefile targets | `Makefile` |

### What Phase 2 Needs From Phase 1

Phase 2 (unit tests) will `import` from `tests.factories` and use `db`, `workspace`, `agent`, `auth_client` fixtures. All of these must work reliably before Phase 2 starts.
