"""Purge conversations older than workspace retention window."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import delete, select

from app.database import async_session_factory, engine
from app.models.organizational import Workspace
from app.models.conversations import Conversation
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def purge_old_data() -> dict:
    return asyncio.run(_purge())


async def _purge() -> dict:
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

            await session.commit()
            return {"status": "success", "total_deleted": total_deleted}
        except Exception:
            await session.rollback()
            raise
