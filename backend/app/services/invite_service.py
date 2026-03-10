import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invites import WorkspaceInvite
from app.models.organizational import Agent, WorkspaceMembership


async def create_invite(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    email: str,
    role: str,
    invited_by_id: uuid.UUID,
) -> WorkspaceInvite:
    token = secrets.token_urlsafe(32)
    invite = WorkspaceInvite(
        workspace_id=workspace_id,
        email=email,
        role=role,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        invited_by_id=invited_by_id,
    )
    db.add(invite)
    await db.flush()
    return invite


async def accept_invite(
    db: AsyncSession,
    token: str,
    full_name: str,
    password: str,
) -> Agent:
    result = await db.execute(
        select(WorkspaceInvite).where(
            WorkspaceInvite.token == token,
            WorkspaceInvite.accepted_at.is_(None),
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or already accepted")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite has expired")

    # Find or create agent
    agent_result = await db.execute(select(Agent).where(Agent.email == invite.email))
    agent = agent_result.scalar_one_or_none()

    if not agent:
        from app.services.auth_service import hash_password

        agent = Agent(
            workspace_id=invite.workspace_id,
            email=invite.email,
            name=full_name,
            password_hash=hash_password(password),
        )
        db.add(agent)
        await db.flush()

    # Create membership if not already a member
    existing_membership = await db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.agent_id == agent.id,
            WorkspaceMembership.workspace_id == invite.workspace_id,
        )
    )
    if not existing_membership.scalar_one_or_none():
        membership = WorkspaceMembership(
            agent_id=agent.id,
            workspace_id=invite.workspace_id,
            role=invite.role,
        )
        db.add(membership)

    invite.accepted_at = datetime.now(timezone.utc)
    return agent


async def list_invites(db: AsyncSession, workspace_id: uuid.UUID) -> list[WorkspaceInvite]:
    result = await db.execute(
        select(WorkspaceInvite)
        .where(WorkspaceInvite.workspace_id == workspace_id)
        .order_by(WorkspaceInvite.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_invite(db: AsyncSession, workspace_id: uuid.UUID, invite_id: uuid.UUID) -> None:
    result = await db.execute(
        select(WorkspaceInvite).where(
            WorkspaceInvite.id == invite_id,
            WorkspaceInvite.workspace_id == workspace_id,
        )
    )
    invite = result.scalar_one_or_none()
    if invite:
        await db.delete(invite)
