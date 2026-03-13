"""Celery task: run autoconfig for a chatbot after crawl ingestion completes."""
import asyncio
import logging
import uuid

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory, engine
from app.services import autoconfig_service
from app.services.realtime import emit_to_workspace
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_autoconfig_for_chatbot(self, chatbot_id: str) -> dict:
    try:
        asyncio.run(_run(uuid.UUID(chatbot_id)))
        return {"status": "ok", "chatbot_id": chatbot_id}
    except MaxRetriesExceededError:
        asyncio.run(_mark_setup_failed(uuid.UUID(chatbot_id)))
        return {"status": "failed", "chatbot_id": chatbot_id}
    except Exception as exc:
        raise self.retry(exc=exc)


async def _run(chatbot_id: uuid.UUID) -> None:
    await engine.dispose()
    from app.models.knowledge import Chatbot

    async with async_session_factory() as session:
        result = await session.execute(
            select(Chatbot)
            .options(selectinload(Chatbot.knowledge_bases))
            .where(Chatbot.id == chatbot_id)
        )
        chatbot = result.scalar_one_or_none()
        if chatbot is None:
            return
        if not chatbot.knowledge_bases:
            return
        kb = chatbot.knowledge_bases[0]
        chatbot = await autoconfig_service.run(session, chatbot.id, kb.id, chatbot.workspace_id)
        chatbot.setup_status = "ready"
        await session.commit()

        await emit_to_workspace(str(chatbot.workspace_id), "chatbot:status_changed", {
            "chatbot_id": str(chatbot_id),
            "setup_status": "ready",
        })


async def _mark_setup_failed(chatbot_id: uuid.UUID) -> None:
    await engine.dispose()
    from app.models.knowledge import Chatbot

    async with async_session_factory() as session:
        result = await session.execute(select(Chatbot).where(Chatbot.id == chatbot_id))
        chatbot = result.scalar_one_or_none()
        if chatbot and chatbot.setup_status == "configuring":
            chatbot.setup_status = "setup_failed"
            await session.commit()

            await emit_to_workspace(str(chatbot.workspace_id), "chatbot:status_changed", {
                "chatbot_id": str(chatbot_id),
                "setup_status": "setup_failed",
            })
