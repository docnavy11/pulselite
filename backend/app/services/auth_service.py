import uuid
from datetime import timedelta

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.organizational import Agent, Workspace, WorkspaceMembership
from app.utils.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


def _slugify(name: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9-]", "-", name.lower().strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    # Append a short unique suffix to guarantee global uniqueness
    suffix = str(uuid.uuid4())[:8]
    return f"{slug or 'workspace'}-{suffix}"


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
    name: str,
    workspace_name: str,
) -> tuple[Agent, Workspace, dict]:
    result = await db.execute(select(Agent).where(Agent.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    workspace = Workspace(name=workspace_name, slug=_slugify(workspace_name))
    db.add(workspace)
    await db.flush()

    agent = Agent(
        workspace_id=workspace.id,
        email=email,
        name=name,
        password_hash=hash_password(password),
    )
    db.add(agent)
    await db.flush()

    membership = WorkspaceMembership(
        agent_id=agent.id,
        workspace_id=workspace.id,
        role="owner",
    )
    db.add(membership)
    await db.flush()

    tokens = await _create_tokens(agent)
    return agent, workspace, tokens


async def authenticate_user(db: AsyncSession, email: str, password: str) -> tuple[Agent, dict]:
    result = await db.execute(select(Agent).where(Agent.email == email))
    agent = result.scalar_one_or_none()
    if agent is None or agent.password_hash is None or not verify_password(password, agent.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    tokens = await _create_tokens(agent)
    return agent, tokens


async def refresh_tokens(refresh_token: str) -> dict:
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    agent_id = payload.get("sub")
    stored = await redis_client.get(f"refresh_token:{agent_id}")
    if stored != refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or expired")

    new_access = create_access_token({"sub": agent_id})
    new_refresh = create_refresh_token({"sub": agent_id})

    ttl = int(timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
    await redis_client.set(f"refresh_token:{agent_id}", new_refresh, ex=ttl)

    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}


async def google_oauth_callback(db: AsyncSession, google_user: dict) -> tuple[Agent, dict]:
    email = google_user["email"]
    result = await db.execute(select(Agent).where(Agent.email == email))
    agent = result.scalar_one_or_none()

    if agent is None:
        workspace = Workspace(name=f"{google_user['name']}'s Workspace", slug=_slugify(email.split("@")[0]))
        db.add(workspace)
        await db.flush()

        agent = Agent(
            workspace_id=workspace.id,
            email=email,
            name=google_user["name"],
            avatar_url=google_user.get("picture"),
            google_id=google_user.get("sub"),
        )
        db.add(agent)
        await db.flush()

        membership = WorkspaceMembership(agent_id=agent.id, workspace_id=workspace.id, role="owner")
        db.add(membership)
        await db.flush()

    tokens = await _create_tokens(agent)
    return agent, tokens


async def _create_tokens(agent: Agent) -> dict:
    agent_id = str(agent.id)
    access_token = create_access_token({"sub": agent_id})
    refresh_token = create_refresh_token({"sub": agent_id})

    ttl = int(timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
    await redis_client.set(f"refresh_token:{agent_id}", refresh_token, ex=ttl)

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
