import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import IntegrationConfig

logger = logging.getLogger(__name__)


async def _get_slack_config(session: AsyncSession, workspace_id: uuid.UUID) -> dict | None:
    result = await session.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "slack",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    config = result.scalar_one_or_none()
    return config.config if config else None


async def send_escalation_alert(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    escalation_reason: str | None,
    confidence_avg: float | None,
    contact_name: str | None,
    contact_email: str | None,
    last_message: str | None,
) -> bool:
    config = await _get_slack_config(session, workspace_id)
    if not config or not config.get("webhook_url"):
        return False

    try:
        from slack_sdk.webhook import WebhookClient

        webhook = WebhookClient(config["webhook_url"])

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Escalated Conversation"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Reason:* {escalation_reason or 'Unknown'}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Confidence:* {confidence_avg:.2f}" if confidence_avg else "*Confidence:* N/A",
                    },
                    {"type": "mrkdwn", "text": f"*Contact:* {contact_name or 'Anonymous'}"},
                    {"type": "mrkdwn", "text": f"*Email:* {contact_email or 'N/A'}"},
                ],
            },
        ]

        if last_message:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Last message:*\n>{last_message[:500]}"},
                }
            )

        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View in Pulse"},
                        "url": f"{config.get('app_url', 'http://localhost:3000')}/exceptions/{conversation_id}",
                    },
                ],
            }
        )

        response = webhook.send(blocks=blocks)
        return response.status_code == 200
    except Exception:
        logger.error("Slack escalation alert failed", exc_info=True)
        return False


async def send_weekly_digest(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    stats: dict,
) -> bool:
    config = await _get_slack_config(session, workspace_id)
    if not config or not config.get("webhook_url"):
        return False

    try:
        from slack_sdk.webhook import WebhookClient

        webhook = WebhookClient(config["webhook_url"])

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Pulse Weekly Digest"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Total Conversations:* {stats.get('total', 0)}"},
                    {"type": "mrkdwn", "text": f"*Auto-Resolved:* {stats.get('resolved', 0)}"},
                    {"type": "mrkdwn", "text": f"*Escalated:* {stats.get('escalated', 0)}"},
                    {"type": "mrkdwn", "text": f"*Resolution Rate:* {stats.get('resolution_rate', 0):.0%}"},
                    {"type": "mrkdwn", "text": f"*Avg Confidence:* {stats.get('avg_confidence', 0):.2f}"},
                    {"type": "mrkdwn", "text": f"*New KB Articles:* {stats.get('new_articles', 0)}"},
                ],
            },
        ]

        response = webhook.send(blocks=blocks)
        return response.status_code == 200
    except Exception:
        logger.error("Slack weekly digest failed", exc_info=True)
        return False
