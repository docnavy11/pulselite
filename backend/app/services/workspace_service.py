import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organizational import Workspace, WorkspaceMembership


async def create_workspace(db: AsyncSession, name: str, slug: str, agent_id: uuid.UUID) -> Workspace:
    result = await db.execute(select(Workspace).where(Workspace.slug == slug))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workspace slug already taken")

    workspace = Workspace(name=name, slug=slug)
    db.add(workspace)
    await db.flush()

    membership = WorkspaceMembership(agent_id=agent_id, workspace_id=workspace.id, role="owner")
    db.add(membership)
    await db.flush()

    return workspace


async def list_workspaces(db: AsyncSession, agent_id: uuid.UUID) -> list[Workspace]:
    result = await db.execute(
        select(Workspace)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(WorkspaceMembership.agent_id == agent_id)
    )
    return list(result.scalars().all())


async def get_workspace(db: AsyncSession, workspace_id: uuid.UUID, agent_id: uuid.UUID) -> Workspace:
    result = await db.execute(
        select(Workspace)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(Workspace.id == workspace_id, WorkspaceMembership.agent_id == agent_id)
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace
