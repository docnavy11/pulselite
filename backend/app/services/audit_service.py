import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def record_audit_event(
    db: AsyncSession,
    *,
    workspace_id,
    user_id=None,
    user_email=None,
    action: str,
    resource_type: str = None,
    resource_id: str = None,
    ip_address: str = None,
    details: dict = None,
):
    """Record an audit log entry. Fire-and-forget — never raises."""
    try:
        log = AuditLog(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            ip_address=ip_address,
            details=details,
        )
        db.add(log)
        await db.flush()
    except Exception as e:
        logger.error("Failed to record audit event: %s", e)
