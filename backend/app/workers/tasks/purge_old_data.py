"""Purge conversations older than workspace retention window."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import delete, select

from app.database import async_session_factory, engine
from app.models.organizational import Workspace
from app.models.conversations import Conversation
from app.services.realtime import emit_task_event
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, soft_time_limit=270, time_limit=300)
def purge_old_data(self) -> dict:
    try:
        return asyncio.run(_purge(self.request.id))
    except MaxRetriesExceededError:
        logger.error("purge_old_data failed after max retries")
        return {"status": "failed", "reason": "max retries exceeded"}
    except Exception as exc:
        raise self.retry(exc=exc)


async def _purge(task_id: str) -> dict:
    await engine.dispose()          # REQUIRED — clear stale pool from previous event loop
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                select(Workspace.id, Workspace.data_retention_days).where(Workspace.data_retention_days.is_not(None))
            )
            workspaces = result.all()

            total_deleted = 0
            now = datetime.now(timezone.utc)

            for ws_id, retention_days in workspaces:
                cutoff = now - timedelta(days=retention_days)

                # Collect IDs to purge
                id_result = await session.execute(
                    select(Conversation.id).where(
                        Conversation.workspace_id == ws_id,
                        Conversation.created_at < cutoff,
                    )
                )
                conv_ids = [row[0] for row in id_result.all()]

                if not conv_ids:
                    continue

                await emit_task_event(str(ws_id), "started", "purge_data", task_id,
                                      detail=f"Purging {len(conv_ids)} conversations")

                # Delete child rows first to avoid FK violations
                from app.models.conversations import (
                    Message,
                    MessageFeedback,
                    ConversationTag,
                )
                from app.models.intelligence import ConversationAnalysis

                await session.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
                await session.execute(delete(MessageFeedback).where(MessageFeedback.conversation_id.in_(conv_ids)))
                await session.execute(delete(ConversationTag).where(ConversationTag.conversation_id.in_(conv_ids)))
                await session.execute(
                    delete(ConversationAnalysis).where(ConversationAnalysis.conversation_id.in_(conv_ids))
                )
                await session.execute(delete(Conversation).where(Conversation.id.in_(conv_ids)))
                deleted = len(conv_ids)
                total_deleted += deleted
                if deleted:
                    logger.info(f"Workspace {ws_id}: purged {deleted} conversations older than {retention_days} days")

                await emit_task_event(str(ws_id), "completed", "purge_data", task_id,
                                      detail=f"Purged {deleted} conversations")

            await session.commit()
            return {"status": "success", "total_deleted": total_deleted}
        except Exception:
            await session.rollback()
            raise
