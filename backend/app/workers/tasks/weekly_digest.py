import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.database import async_session_factory, engine
from app.models.conversations import Conversation
from app.models.knowledge import Article
from app.models.organizational import Workspace
from app.services.integrations.email import send_weekly_digest_email
from app.services.integrations.slack import send_weekly_digest
from app.models.intelligence import ConversationAnalysis, GapCluster
from app.services.realtime import emit_task_event
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def send_weekly_digest_task(self) -> dict:
    return asyncio.run(_send_digests(self.request.id))


async def _send_digests(task_id: str) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        try:
            result = await session.execute(select(Workspace.id))
            workspace_ids = [row[0] for row in result.all()]

            sent = 0
            for ws_id in workspace_ids:
                stats = await _compute_weekly_stats(session, ws_id)
                if stats["total"] == 0:
                    continue
                await emit_task_event(ws_id, "started", "weekly_digest", task_id)
                await send_weekly_digest(session, ws_id, stats)
                await send_weekly_digest_email(session, ws_id, stats)
                sent += 1
                await emit_task_event(ws_id, "completed", "weekly_digest", task_id)

            return {"status": "success", "digests_sent": sent}
        except Exception:
            logger.exception("Weekly digest failed")
            raise


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

    # Intelligence stats
    confidence_result = await session.execute(
        select(func.avg(Conversation.confidence_avg))
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= week_start,
            Conversation.confidence_avg.isnot(None),
        )
    )
    avg_confidence = confidence_result.scalar() or 0.0

    open_gaps_result = await session.execute(
        select(func.count())
        .select_from(GapCluster)
        .where(GapCluster.workspace_id == workspace_id, GapCluster.status == "open")
    )
    open_gaps = open_gaps_result.scalar() or 0

    sentiment_result = await session.execute(
        select(func.avg(ConversationAnalysis.sentiment_score))
        .where(
            ConversationAnalysis.workspace_id == workspace_id,
            ConversationAnalysis.created_at >= week_start,
            ConversationAnalysis.sentiment_score.isnot(None),
        )
    )
    avg_sentiment = sentiment_result.scalar()

    return {
        "total": total,
        "resolved": resolved,
        "escalated": escalated,
        "new_articles": new_articles,
        "resolution_rate": resolution_rate,
        "avg_confidence": round(float(avg_confidence), 3),
        "open_gaps": open_gaps,
        "avg_sentiment": round(float(avg_sentiment), 3) if avg_sentiment is not None else None,
    }
