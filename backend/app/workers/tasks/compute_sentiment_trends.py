import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import func, select

from app.database import async_session_factory, engine
from app.models.intelligence import ConversationAnalysis
from app.models.organizational import Workspace
from app.services.realtime import emit_task_event
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

ALERT_THRESHOLD = -0.3


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, soft_time_limit=270, time_limit=300)
def compute_sentiment_trends(self) -> dict:
    try:
        return asyncio.run(_compute(self.request.id))
    except MaxRetriesExceededError:
        logger.error("compute_sentiment_trends failed after max retries")
        return {"status": "failed", "reason": "max retries exceeded"}
    except Exception as exc:
        raise self.retry(exc=exc)


async def _compute(task_id: str) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        try:
            result = await session.execute(select(Workspace.id, Workspace.intelligence_config))
            workspace_ids = [
                row[0] for row in result.all()
                if (row[1] or {}).get("sentiment_trends", True)
            ]

            alerts = []
            for ws_id in workspace_ids:
                ws_task_id = f"{task_id}:{ws_id}"
                await emit_task_event(ws_id, "started", "compute_sentiment", ws_task_id)
                alert = await _compute_workspace(session, ws_id)
                if alert:
                    alerts.append(str(ws_id))
                await emit_task_event(ws_id, "completed", "compute_sentiment", ws_task_id)

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
