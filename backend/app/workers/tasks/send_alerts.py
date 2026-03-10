import asyncio
import logging
import uuid

from sqlalchemy import or_, select

from app.database import async_session_factory
from app.models.contacts import Contact
from app.models.conversations import Conversation, Message
from app.models.integrations import IntegrationConfig
from app.services.integrations.email import send_escalation_email
from app.services.integrations.slack import send_escalation_alert
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def send_escalation_alerts(conversation_id: str, workspace_id: str) -> dict:
    return asyncio.run(_send(uuid.UUID(conversation_id), uuid.UUID(workspace_id)))


async def _send(conversation_id: uuid.UUID, workspace_id: uuid.UUID) -> dict:
    async with async_session_factory() as session:
        try:
            result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
            conv = result.scalar_one_or_none()
            if not conv:
                return {"status": "error", "detail": "Conversation not found"}

            # Check optional alert threshold from integration config
            config_result = await session.execute(
                select(IntegrationConfig).where(
                    IntegrationConfig.workspace_id == workspace_id,
                    or_(
                        IntegrationConfig.integration_type == "slack",
                        IntegrationConfig.integration_type == "email",
                    ),
                    IntegrationConfig.is_active == True,  # noqa: E712
                )
            )
            for cfg in config_result.scalars().all():
                # alert_max_confidence: skip alerting when bot was confident enough.
                # Alerts are sent only for conversations where confidence < threshold.
                max_conf = cfg.config.get("alert_max_confidence") or cfg.config.get("alert_min_confidence")
                if max_conf is not None and conv.confidence_avg is not None:
                    if conv.confidence_avg >= float(max_conf):
                        return {"status": "skipped", "reason": "confidence_above_threshold"}

            contact_name = None
            contact_email = None
            if conv.contact_id:
                contact_result = await session.execute(
                    select(Contact.name, Contact.email).where(Contact.id == conv.contact_id)
                )
                row = contact_result.first()
                if row:
                    contact_name, contact_email = row

            msg_result = await session.execute(
                select(Message.content)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            msg_row = msg_result.first()
            last_message = msg_row[0] if msg_row else None

            slack_sent = await send_escalation_alert(
                session,
                workspace_id,
                conversation_id,
                conv.escalation_reason,
                conv.confidence_avg,
                contact_name,
                contact_email,
                last_message,
            )

            email_sent = await send_escalation_email(
                session,
                workspace_id,
                conversation_id,
                conv.escalation_reason,
                contact_name,
                last_message,
            )

            return {
                "status": "success",
                "slack": slack_sent,
                "email": email_sent,
            }
        except Exception as e:
            logger.error(f"Alert sending failed: {e}")
            return {"status": "error", "detail": str(e)}
