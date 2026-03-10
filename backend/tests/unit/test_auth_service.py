"""Unit tests for app.services.auth_service — register and login."""
import pytest
from unittest.mock import AsyncMock
from fastapi import HTTPException
from app.services.auth_service import register_user, authenticate_user


@pytest.mark.asyncio
async def test_register_creates_workspace_agent_membership(db, mocker):
    """register_user returns (Agent, Workspace, tokens) and creates all three rows."""
    mocker.patch("app.services.auth_service.redis_client.set", new_callable=AsyncMock)

    agent, workspace, tokens = await register_user(
        db,
        email="newuser@example.com",
        password="SecurePass123!",
        name="New User",
        workspace_name="New Workspace",
    )

    assert agent.email == "newuser@example.com"
    assert agent.name == "New User"
    assert workspace.name == "New Workspace"
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email_raises_409(db, mocker):
    """A second registration with the same email raises HTTP 409."""
    mocker.patch("app.services.auth_service.redis_client.set", new_callable=AsyncMock)

    await register_user(
        db,
        email="dup@example.com",
        password="Pass123!",
        name="A",
        workspace_name="WS1",
    )

    with pytest.raises(HTTPException) as exc_info:
        await register_user(
            db,
            email="dup@example.com",
            password="Pass456!",
            name="B",
            workspace_name="WS2",
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_authenticate_correct_credentials(db, agent, mocker):
    """authenticate_user returns (Agent, tokens) for valid credentials."""
    mocker.patch("app.services.auth_service.redis_client.set", new_callable=AsyncMock)

    result_agent, tokens = await authenticate_user(
        db, email=agent.email, password="testpassword123"
    )

    assert result_agent.id == agent.id
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_authenticate_wrong_password_raises_401(db, agent, mocker):
    """authenticate_user raises HTTP 401 when the password is wrong."""
    mocker.patch("app.services.auth_service.redis_client.set", new_callable=AsyncMock)

    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(db, email=agent.email, password="wrongpassword")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_authenticate_unknown_email_raises_401(db, mocker):
    """authenticate_user raises HTTP 401 when the email does not exist."""
    mocker.patch("app.services.auth_service.redis_client.set", new_callable=AsyncMock)

    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(db, email="nobody@nowhere.com", password="anypassword")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_register_workspace_slug_is_url_friendly(db, mocker):
    """register_user slugifies the workspace name (lowercase, no spaces)."""
    mocker.patch("app.services.auth_service.redis_client.set", new_callable=AsyncMock)

    _, workspace, _ = await register_user(
        db,
        email="slug@example.com",
        password="Pass123!",
        name="X",
        workspace_name="My Awesome Co",
    )

    import re
    assert workspace.slug is not None
    assert " " not in workspace.slug
    assert workspace.slug == workspace.slug.lower()
    # _slugify() appends a short UUID4 hex suffix for global uniqueness,
    # e.g. "my-awesome-co-ae105bd8"
    assert workspace.slug.startswith("my-awesome-co-")
    assert re.match(r"^[a-z0-9][a-z0-9-]*$", workspace.slug)
