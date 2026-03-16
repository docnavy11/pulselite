"""
Global pytest fixtures for the Pulse test suite.

Architecture:
  - 'engine': one per session, connects to pulse_test DB
  - 'db': one per test, wraps all writes in a SAVEPOINT that rolls back
  - 'app': FastAPI app with get_db overridden to use the test session
  - 'client': httpx AsyncClient connected to the test app
  - 'workspace', 'agent', 'auth_headers', 'auth_client': pre-seeded entities
"""
import os
import uuid
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

# Point at the test database — override env BEFORE importing app modules
os.environ["POSTGRES_DB"] = "pulse_test"
os.environ["POSTGRES_HOST"] = "postgres"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_USER"] = "pulse"
os.environ["POSTGRES_PASSWORD"] = "pulse_dev_password"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-at-least-32-chars-long")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-chars-long")
os.environ.setdefault("FERNET_KEY", "mVpvOlHdo0cK-apXcA_E3X5DjPkZovNUAlxVgaMW7_E=")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-real")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-not-real")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_not_real")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_not_real")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("AI_API_KEY", "test-ai-key")
os.environ.setdefault("AI_BASE_URL", "https://openrouter.ai/api/v1")

# Import app AFTER env is set
from app.main import create_app
from app.database import get_db


# ── Engine (session-scoped: create once per test run) ────────────────────────

@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    db_url = (
        f"postgresql+psycopg://"
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
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as c:
        yield c


# ── Seeded workspace + agent ──────────────────────────────────────────────────

@pytest_asyncio.fixture
async def workspace(db: AsyncSession):
    """A pre-created test workspace."""
    from app.models.organizational import Workspace
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
    Provides .workspace_id and .agent_id attributes for convenience.
    """
    from app.utils.security import create_access_token
    token = create_access_token({"sub": str(agent.id), "type": "access"})
    client.headers.update({"Authorization": f"Bearer {token}"})
    client.workspace_id = str(workspace.id)
    client.agent_id = str(agent.id)
    return client


# ── Auth headers factory (for multi-workspace isolation tests) ────────────────

async def make_auth_headers_for(ag) -> dict[str, str]:
    """
    Generate a valid JWT Authorization header for any agent.
    Use this in isolation tests where you need multiple agents.
    """
    from app.utils.security import create_access_token
    token = create_access_token({"sub": str(ag.id), "type": "access"})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def second_workspace(db: AsyncSession):
    """A second workspace, completely separate from the first."""
    from app.models.organizational import Workspace
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
