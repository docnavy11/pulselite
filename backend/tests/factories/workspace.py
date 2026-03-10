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
        workspace_id=workspace.id,
        email=email or f"user-{uuid.uuid4().hex[:8]}@pulse.test",
        name=name,
        password_hash=hash_password(password),
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
