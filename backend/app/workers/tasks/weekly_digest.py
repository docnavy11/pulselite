import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.database import async_session_factory
from app.models.conversations import Conversation
from app.models.knowledge import Article
from app.models.organizational import Workspace
from app.services.integrations.email import send_weekly_digest_email
from app.services.integrations.slack import send_weekly_digest
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def send_weekly_digest_task() -> dict:
    return asyncio.run(_send_digests())


async def _send_digests() -> dict:
    async with async_session_factory() as session:
        try:
            result = await session.execute(select(Workspace.id))
            workspace_ids = [row[0] for row in result.all()]

            sent = 0
            for ws_id in workspace_ids:
                stats = await _compute_weekly_stats(session, ws_id)
                if stats["total"] == 0:
                    continue

                await send_weekly_digest(session, ws_id, stats)
                await send_weekly_digest_email(session, ws_id, stats)
                sent += 1

            return {"status": "success", "digests_sent": sent}
        except Exception as e:
            logger.error(f"Weekly digest failed: {e}")
            return {"status": "error", "detail": str(e)}


async def _compute_weekly_stats(session, workspace_id: uuid.UUID) -> dict:
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)

    total_result = await session.execute(
        select(func.count())
        .select_from(Conversation)
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= week_start,
        )
    )
    total = total_result.scalar() or 0

    resolved_result = await session.execute(
        select(func.count())
        .select_from(Conversation)
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= week_start,
            Conversation.autonomous_resolved == True,  # noqa: E712
        )
    )
    resolved = resolved_result.scalar() or 0

    escalated_result = await session.execute(
        select(func.count())
        .select_from(Conversation)
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= week_start,
            Conversation.escalation_reason.isnot(None),
        )
    )
    escalated = escalated_result.scalar() or 0

    articles_result = await session.execute(
        select(func.count())
        .select_from(Article)
        .where(
            Article.workspace_id == workspace_id,
            Article.created_at >= week_start,
            Article.state == "published",
        )
    )
    new_articles = articles_result.scalar() or 0

    resolution_rate = resolved / total if total > 0 else 0.0

    return {
        "total": total,
        "resolved": resolved,
        "escalated": escalated,
        "new_articles": new_articles,
        "resolution_rate": resolution_rate,
        "avg_confidence": 0.0,
    }
