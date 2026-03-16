import asyncio
import logging
from datetime import datetime, timedelta, timezone

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select, update

from app.database import async_session_factory, engine
from app.models.conversations import Conversation
from app.models.intelligence import ConversationAnalysis
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Conversations with no new messages for this long are auto-closed
STALE_MINUTES = 30


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, soft_time_limit=110, time_limit=120)
def close_stale_conversations(self) -> dict:
    try:
        return asyncio.run(_close_stale(self.request.id))
    except MaxRetriesExceededError:
        logger.error("close_stale_conversations failed after max retries")
        return {"status": "failed", "reason": "max retries exceeded"}
    except Exception as exc:
        raise self.retry(exc=exc)


async def _close_stale(task_id: str) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_MINUTES)

            # Find open conversations that haven't been updated recently
            result = await session.execute(
                select(Conversation.id, Conversation.workspace_id)
                .where(
                    Conversation.status == "open",
                    Conversation.updated_at < cutoff,
                )
            )
            stale = result.all()

            if not stale:
                return {"status": "ok", "closed": 0}

            conv_ids = [row[0] for row in stale]

            # Close them
            await session.execute(
                update(Conversation)
                .where(Conversation.id.in_(conv_ids))
                .values(
                    status="resolved",
                    resolved_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

            # Trigger analysis for conversations that don't have one yet
            analyzed_result = await session.execute(
                select(ConversationAnalysis.conversation_id)
                .where(ConversationAnalysis.conversation_id.in_(conv_ids))
            )
            already_analyzed = {row[0] for row in analyzed_result.all()}

            from app.workers.tasks.analyze_conversation import analyze_conversation

            queued = 0
            for conv_id, ws_id in stale:
                if conv_id not in already_analyzed:
                    analyze_conversation.delay(str(conv_id), str(ws_id))  # type: ignore[attr-defined]
                    queued += 1

            logger.info(
                f"Auto-closed {len(conv_ids)} stale conversations, "
                f"queued {queued} for analysis"
            )
            return {"status": "ok", "closed": len(conv_ids), "analysis_queued": queued}
        except Exception:
            await session.rollback()
            raise
