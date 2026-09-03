"""Seed script: creates a test user for easy local development."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.organizational import Agent, Workspace, WorkspaceMembership
from app.utils.security import hash_password

TEST_EMAIL = "test@pulse.dev"
TEST_PASSWORD = "Test1234"
TEST_NAME = "Test User"
WORKSPACE_SLUG = "test-workspace"
WORKSPACE_NAME = "Test Workspace"


async def seed():
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "pulse")
    user = os.environ.get("POSTGRES_USER", "pulse")
    password = os.environ.get("POSTGRES_PASSWORD", "pulse_dev_password")
    url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"

    engine = create_async_engine(url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if test agent already exists
        result = await session.execute(select(Agent).where(Agent.email == TEST_EMAIL))
        if result.scalar_one_or_none():
            print(f"Test user already exists: {TEST_EMAIL} / {TEST_PASSWORD}")
            await engine.dispose()
            return

        # Get or create workspace
        result = await session.execute(select(Workspace).where(Workspace.slug == WORKSPACE_SLUG))
        workspace = result.scalar_one_or_none()
        if not workspace:
            workspace = Workspace(name=WORKSPACE_NAME, slug=WORKSPACE_SLUG)
            session.add(workspace)
            await session.flush()

        # Create agent linked to workspace
        agent = Agent(
            workspace_id=workspace.id,
            email=TEST_EMAIL,
            password_hash=hash_password(TEST_PASSWORD),
            name=TEST_NAME,
        )
        session.add(agent)
        await session.flush()

        # Create ownership membership
        membership = WorkspaceMembership(
            agent_id=agent.id,
            workspace_id=workspace.id,
            role="owner",
        )
        session.add(membership)
        await session.commit()

        print(f"Seeded test user:")
        print(f"  Email:    {TEST_EMAIL}")
        print(f"  Password: {TEST_PASSWORD}")
        print(f"  Workspace: {WORKSPACE_NAME}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
