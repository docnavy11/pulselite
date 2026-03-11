import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from app.database import async_session_factory, engine
from app.models.intelligence import ConversationAnalysis
from app.models.organizational import Workspace
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

ALERT_THRESHOLD = -0.3


@celery_app.task
def compute_sentiment_trends() -> dict:
    return asyncio.run(_compute())


async def _compute() -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        try:
            result = await session.execute(select(Workspace.id))
            workspace_ids = [row[0] for row in result.all()]

            alerts = []
            for ws_id in workspace_ids:
                alert = await _compute_workspace(session, ws_id)
                if alert:
                    alerts.append(str(ws_id))

            await session.commit()
            return {"status": "success", "alerts": alerts}
        except Exception:
            await session.rollback()
            raise


async def _compute_workspace(session, workspace_id: uuid.UUID) -> bool:
    yesterday = date.today() - timedelta(days=1)
    day_start = datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    result = await session.execute(
        select(func.avg(ConversationAnalysis.sentiment_score)).where(
            ConversationAnalysis.workspace_id == workspace_id,
            ConversationAnalysis.sentiment_score.isnot(None),
            ConversationAnalysis.created_at >= day_start,
            ConversationAnalysis.created_at < day_end,
        )
    )
    avg_sentiment = result.scalar()

    if avg_sentiment is None:
        return False

    if avg_sentiment < ALERT_THRESHOLD:
        logger.warning(
            f"Sentiment alert for workspace {workspace_id}: avg={avg_sentiment:.2f} (threshold={ALERT_THRESHOLD})"
        )
        return True

    return False
