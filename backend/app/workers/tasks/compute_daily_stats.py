import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.conversations import Conversation
from app.models.intelligence import GapCluster, GapEvent, RetrievalLog
from app.models.knowledge import Chatbot
from app.models.organizational import Workspace
from app.workers.celery_app import celery_app


@celery_app.task
def compute_daily_stats() -> dict:
    return asyncio.run(_compute())


async def _compute() -> dict:
    async with async_session_factory() as session:
        try:
            yesterday = date.today() - timedelta(days=1)
            day_start = datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1)

            result = await session.execute(select(Workspace.id))
            workspace_ids = [row[0] for row in result.all()]

            total_upserts = 0
            for ws_id in workspace_ids:
                result = await session.execute(select(Chatbot.id).where(Chatbot.workspace_id == ws_id))
                chatbot_ids = [row[0] for row in result.all()]
                chatbot_ids.append(None)

                for cb_id in chatbot_ids:
                    stats = await _compute_for_pair(session, ws_id, cb_id, yesterday, day_start, day_end)
                    if stats["total_conversations"] > 0:
                        total_upserts += 1

            await session.commit()
            return {"status": "success", "upserts": total_upserts, "date": str(yesterday)}
        except Exception:
            await session.rollback()
            raise


async def _compute_for_pair(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    chatbot_id: uuid.UUID | None,
    period_date: date,
    day_start: datetime,
    day_end: datetime,
) -> dict:
    conv_query = select(
        func.count().label("total"),
        func.count().filter(Conversation.autonomous_resolved == True).label("auto_resolved"),  # noqa: E712
        func.count().filter(Conversation.outcome == "escalated_to_human").label("escalated"),
        func.count().filter(Conversation.outcome == "abandoned").label("abandoned"),
    ).where(
        Conversation.workspace_id == workspace_id,
        Conversation.created_at >= day_start,
        Conversation.created_at < day_end,
    )
    if chatbot_id:
        conv_query = conv_query.where(Conversation.chatbot_id == chatbot_id)

    result = await session.execute(conv_query)
    row = result.one()

    avg_conf_query = select(func.avg(RetrievalLog.confidence_score)).where(
        RetrievalLog.workspace_id == workspace_id,
        RetrievalLog.created_at >= day_start,
        RetrievalLog.created_at < day_end,
    )
    if chatbot_id:
        avg_conf_query = avg_conf_query.where(RetrievalLog.chatbot_id == chatbot_id)
    avg_conf_result = await session.execute(avg_conf_query)
    avg_confidence = avg_conf_result.scalar()

    new_gaps_query = (
        select(func.count())
        .select_from(GapEvent)
        .where(
            GapEvent.workspace_id == workspace_id,
            GapEvent.created_at >= day_start,
            GapEvent.created_at < day_end,
        )
    )
    new_gaps = (await session.execute(new_gaps_query)).scalar() or 0

    resolved_gaps_query = (
        select(func.count())
        .select_from(GapCluster)
        .where(
            GapCluster.workspace_id == workspace_id,
            GapCluster.resolved_at >= day_start,
            GapCluster.resolved_at < day_end,
        )
    )
    if chatbot_id:
        resolved_gaps_query = resolved_gaps_query.where(GapCluster.chatbot_id == chatbot_id)
    resolved_gaps = (await session.execute(resolved_gaps_query)).scalar() or 0

    knowledge_velocity = resolved_gaps / new_gaps if new_gaps > 0 else 0.0

    open_gaps_query = (
        select(func.count())
        .select_from(GapCluster)
        .where(
            GapCluster.workspace_id == workspace_id,
            GapCluster.status == "open",
        )
    )
    if chatbot_id:
        open_gaps_query = open_gaps_query.where(GapCluster.chatbot_id == chatbot_id)
    doc_debt = (await session.execute(open_gaps_query)).scalar() or 0

    return {
        "total_conversations": row.total,
        "autonomously_resolved": row.auto_resolved,
        "escalated_to_human": row.escalated,
        "abandoned": row.abandoned,
        "avg_confidence_score": float(avg_confidence) if avg_confidence else None,
        "knowledge_velocity": knowledge_velocity,
        "documentation_debt": doc_debt,
    }


