"""Integration tests for POST /auth/register and POST /auth/login.

Response shape (AuthResponse):
    {
        "user": {"id": ..., "email": ..., "name": ..., ...},
        "tokens": {
            "access_token": ...,
            "refresh_token": ...,
            "token_type": "bearer"
        }
    }

Note: /auth/register has no explicit status_code, so it returns 200.
      /auth/login also returns AuthResponse (200) on success.

      The global `agent` fixture uses @pulse.test domain which Pydantic
      EmailStr rejects — login tests use a local `login_agent` fixture
      with a valid RFC-5321 domain (@example.com).
"""
import uuid
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock


@pytest.fixture(autouse=True)
def mock_redis(mocker):
    """Mock Redis calls in auth_service so tests don't need a live Redis."""
    mocker.patch(
        "app.services.auth_service.redis_client.set",
        new_callable=AsyncMock,
    )
    mocker.patch(
        "app.services.auth_service.redis_client.get",
        new_callable=AsyncMock,
        return_value=None,
    )


@pytest.fixture(autouse=True)
def disable_rate_limit(mocker):
    """Disable the SlowAPI rate limiter so register/login tests don't hit 429."""
    mocker.patch("app.api.v1.public_chat.limiter.enabled", new=False)


@pytest_asyncio.fixture
async def login_agent(db):
    """Agent with a valid RFC-5321 email (example.com) for login endpoint tests."""
    from app.models.organizational import Agent, Workspace, WorkspaceMembership
    from app.utils.security import hash_password

    ws = Workspace(
        id=uuid.uuid4(),
        name="Login Test WS",
        slug=f"login-ws-{uuid.uuid4().hex[:8]}",
        plan="pro",
    )
    db.add(ws)
    await db.flush()

    ag = Agent(
        id=uuid.uuid4(),
        email=f"logintest-{uuid.uuid4().hex[:8]}@example.com",
        name="Login Test Agent",
        password_hash=hash_password("testpassword123"),
        workspace_id=ws.id,
    )
    db.add(ag)
    await db.flush()

    membership = WorkspaceMembership(
        agent_id=ag.id,
        workspace_id=ws.id,
        role="owner",
    )
    db.add(membership)
    await db.flush()
    return ag


# ── Register ──────────────────────────────────────────────────────────────────

async def test_register_returns_200(client):
    r = await client.post("/api/v1/auth/register", json={
        "email": "reg@test.com",
        "password": "SecurePass123!",
        "name": "Reg User",
        "workspace_name": "Reg WS",
    })
    assert r.status_code == 200


async def test_register_response_has_tokens(client):
    r = await client.post("/api/v1/auth/register", json={
        "email": "tok@test.com",
        "password": "SecurePass123!",
        "name": "Token User",
        "workspace_name": "Token WS",
    })
    assert r.status_code == 200
    data = r.json()
    assert "tokens" in data
    tokens = data["tokens"]
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens.get("token_type") == "bearer"


async def test_register_response_has_user(client):
    r = await client.post("/api/v1/auth/register", json={
        "email": "usr@test.com",
        "password": "SecurePass123!",
        "name": "Some User",
        "workspace_name": "Some WS",
    })
    assert r.status_code == 200
    data = r.json()
    assert "user" in data
    assert data["user"]["email"] == "usr@test.com"
    assert data["user"]["name"] == "Some User"


async def test_register_duplicate_email_returns_409(client):
    payload = {
        "email": "dup@test.com",
        "password": "Pass123!",
        "name": "A",
        "workspace_name": "W",
    }
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 200
    r2 = await client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409


async def test_register_missing_field_returns_422(client):
    r = await client.post("/api/v1/auth/register", json={"email": "x@x.com"})
    assert r.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

async def test_login_correct_credentials_returns_200(client, login_agent):
    r = await client.post("/api/v1/auth/login", json={
        "email": login_agent.email,
        "password": "testpassword123",
    })
    assert r.status_code == 200
    data = r.json()
    assert "tokens" in data
    assert "access_token" in data["tokens"]


async def test_login_wrong_password_returns_401(client, login_agent):
    r = await client.post("/api/v1/auth/login", json={
        "email": login_agent.email,
        "password": "wrongpassword",
    })
    assert r.status_code == 401


async def test_login_unknown_email_returns_401(client):
    r = await client.post("/api/v1/auth/login", json={
        "email": "nobody@nowhere.com",
        "password": "anypassword",
    })
    assert r.status_code == 401


async def test_login_missing_fields_returns_422(client):
    r = await client.post("/api/v1/auth/login", json={"email": "x@x.com"})
    assert r.status_code == 422


async def test_login_response_has_user(client, login_agent):
    r = await client.post("/api/v1/auth/login", json={
        "email": login_agent.email,
        "password": "testpassword123",
    })
    assert r.status_code == 200
    data = r.json()
    assert "user" in data
    assert data["user"]["email"] == login_agent.email
