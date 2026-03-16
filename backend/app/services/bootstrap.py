"""Auto-bootstrap: creates admin user + workspace on first startup if configured via env."""
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.organizational import Agent, Workspace, WorkspaceMembership
from app.utils.security import hash_password

logger = logging.getLogger(__name__)


async def bootstrap_admin():
    """Create the admin user and default workspace if the DB has no users and env vars are set."""
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        logger.info("ADMIN_EMAIL or ADMIN_PASSWORD not set — skipping admin bootstrap. Set these in .env to auto-create an admin on first startup.")
        return

    async with async_session_factory() as session:
        # Only bootstrap if no users exist at all
        result = await session.execute(select(func.count(Agent.id)))
        user_count = result.scalar_one()
        if user_count > 0:
            return

        # Check if this specific admin already exists (safety net)
        result = await session.execute(
            select(Agent).where(Agent.email == settings.ADMIN_EMAIL)
        )
        if result.scalar_one_or_none():
            return

        # Create default workspace
        workspace = Workspace(name="Default Workspace", slug="default")
        session.add(workspace)
        await session.flush()

        # Create admin agent
        agent = Agent(
            workspace_id=workspace.id,
            email=settings.ADMIN_EMAIL,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            name="Admin",
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

        logger.info(
            "Bootstrapped admin user %s with workspace 'Default Workspace'",
            settings.ADMIN_EMAIL,
        )
