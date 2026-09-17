import logging
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import resend
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import IntegrationConfig
from app.services.encryption import decrypt_api_key

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


def send_email(config: dict, subject: str, html: str) -> bool:
    """Send an email using the configured provider (Resend or SMTP)."""
    provider = config.get("provider", "resend")
    to_email = config.get("to_email")
    from_email = config.get("from_email", "Pulse <notifications@pulse.app>")

    if not to_email:
        return False

    try:
        if provider == "smtp":
            return _send_smtp(config, subject, html, from_email, to_email)
        else:
            return _send_resend(config, subject, html, from_email, to_email)
    except Exception:
        logger.error("Email send failed (%s)", provider, exc_info=True)
        return False


def _send_smtp(config: dict, subject: str, html: str, from_email: str, to_email: str) -> bool:
    host = config.get("host")
    port = config.get("port", 587)
    username = config.get("username")
    raw_password = config.get("password")
    password = decrypt_api_key(raw_password) if raw_password else None

    if not host:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(host, port) as server:
        if config.get("tls", True):
            server.starttls()
        if username and password:
            server.login(username, password)
        server.send_message(msg)
    return True


def _send_resend(config: dict, subject: str, html: str, from_email: str, to_email: str) -> bool:
    raw_api_key = config.get("api_key")
    if not raw_api_key:
        return False

    api_key = decrypt_api_key(raw_api_key)
    resend.api_key = api_key
    resend.Emails.send(
        {
            "from": from_email,
            "to": to_email,
            "subject": subject,
            "html": html,
        }
    )
    return True


async def send_escalation_email(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    escalation_reason: str | None,
    contact_name: str | None,
    last_message: str | None,
) -> bool:
    config = await _get_email_config(session, workspace_id)
    if not config:
        return False

    html = f"""
    <h2>Escalated Conversation</h2>
    <p><strong>Reason:</strong> {escalation_reason or "Unknown"}</p>
    <p><strong>Contact:</strong> {contact_name or "Anonymous"}</p>
    <p><strong>Last message:</strong></p>
    <blockquote>{last_message[:500] if last_message else "N/A"}</blockquote>
    <p><a href="{config.get("app_url", "http://localhost:3000")}/exceptions/{conversation_id}">View in Pulse</a></p>
    """
    subject = f"Escalated: {contact_name or 'Anonymous'} - {escalation_reason or 'Low confidence'}"
    return send_email(config, subject, html)


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
    if not config:
        return False

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
    return send_email(config, "Pulse Weekly Digest", html)
