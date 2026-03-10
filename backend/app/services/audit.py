import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


async def log_audit(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    action: str,
    *,
    actor_id: uuid.UUID | None = None,
    actor_email: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    resource_name: str | None = None,
    ip_address: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Add an audit log entry to the session. Caller is responsible for committing."""
    try:
        log = AuditLog(
            workspace_id=workspace_id,
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            ip_address=ip_address,
            extra_data=metadata,
        )
        session.add(log)
    except Exception:
        logger.exception("Failed to add audit log entry for action=%s", action)
