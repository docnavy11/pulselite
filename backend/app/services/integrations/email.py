import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import IntegrationConfig

logger = logging.getLogger(__name__)


async def _get_email_config(session: AsyncSession, workspace_id: uuid.UUID) -> dict | None:
    result = await session.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "email",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    config = result.scalar_one_or_none()
    return config.config if config else None


async def send_escalation_email(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    escalation_reason: str | None,
    contact_name: str | None,
    last_message: str | None,
) -> bool:
    config = await _get_email_config(session, workspace_id)
    if not config or not config.get("api_key") or not config.get("to_email"):
        return False

    try:
        import resend

        resend.api_key = config["api_key"]

        html = f"""
        <h2>Escalated Conversation</h2>
        <p><strong>Reason:</strong> {escalation_reason or "Unknown"}</p>
        <p><strong>Contact:</strong> {contact_name or "Anonymous"}</p>
        <p><strong>Last message:</strong></p>
        <blockquote>{last_message[:500] if last_message else "N/A"}</blockquote>
        <p><a href="{config.get("app_url", "http://localhost:3000")}/exceptions/{conversation_id}">View in Pulse</a></p>
        """

        resend.Emails.send(
            {
                "from": config.get("from_email", "Pulse <notifications@pulse.app>"),
                "to": config["to_email"],
                "subject": f"Escalated: {contact_name or 'Anonymous'} - {escalation_reason or 'Low confidence'}",
                "html": html,
            }
        )
        return True
    except Exception as e:
        logger.error(f"Email escalation failed: {e}")
        return False


async def send_invite_email(email: str, token: str, _workspace_id: object) -> None:
    """Log invite link. In production, also sends via Resend if configured."""
    invite_url = f"http://localhost:3000/accept-invite?token={token}"
    logger.info(f"Invite link for {email}: {invite_url}")


async def send_weekly_digest_email(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    stats: dict,
) -> bool:
    config = await _get_email_config(session, workspace_id)
    if not config or not config.get("api_key") or not config.get("to_email"):
        return False

    try:
        import resend

        resend.api_key = config["api_key"]

        html = f"""
        <h2>Pulse Weekly Digest</h2>
        <table style="border-collapse: collapse; width: 100%;">
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total Conversations</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{stats.get("total", 0)}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Auto-Resolved</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{stats.get("resolved", 0)}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Escalated</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{stats.get("escalated", 0)}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Resolution Rate</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{stats.get("resolution_rate", 0):.0%}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Avg Confidence</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{stats.get("avg_confidence", 0):.2f}</td></tr>
        </table>
        """

        resend.Emails.send(
            {
                "from": config.get("from_email", "Pulse <notifications@pulse.app>"),
                "to": config["to_email"],
                "subject": "Pulse Weekly Digest",
                "html": html,
            }
        )
        return True
    except Exception as e:
        logger.error(f"Email weekly digest failed: {e}")
        return False
