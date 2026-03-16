"""Celery task: run autoconfig for a chatbot after crawl ingestion completes."""
import asyncio
import logging
import uuid

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory, engine
from app.services import autoconfig_service
from app.services.realtime import emit_to_workspace, clear_chatbot_setup_state
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_autoconfig_for_chatbot(self, chatbot_id: str) -> dict:
    try:
        asyncio.run(_run(uuid.UUID(chatbot_id)))
        return {"status": "ok", "chatbot_id": chatbot_id}
    except MaxRetriesExceededError as exc:
        reason = _describe_error(exc.__cause__ or exc)
        logger.error("Autoconfig failed for chatbot %s after retries: %s", chatbot_id, reason)
        asyncio.run(_mark_setup_failed(uuid.UUID(chatbot_id), reason=reason))
        return {"status": "failed", "chatbot_id": chatbot_id, "reason": reason}
    except Exception as exc:
        raise self.retry(exc=exc)


def _describe_error(exc: BaseException) -> str:
    """Turn an exception into a user-friendly error description."""
    msg = str(exc).lower()
    if "401" in msg or "unauthorized" in msg or "invalid.*key" in msg:
        return "AI provider returned 401 Unauthorized. Check your AI_API_KEY in .env or workspace AI settings."
    if "404" in msg or "not found" in msg:
        return "AI provider returned 404. Check your AI_BASE_URL — the endpoint may be incorrect."
    if "429" in msg or "rate" in msg:
        return "AI provider rate limit exceeded. Wait a moment and try again, or use a different API key."
    if "timeout" in msg or "timed out" in msg:
        return "AI provider request timed out. Check that AI_BASE_URL is reachable from the server."
    if "connection" in msg or "refused" in msg or "unreachable" in msg:
        return "Cannot connect to AI provider. Check that AI_BASE_URL is correct and the service is running."
    if "model" in msg and ("not found" in msg or "does not exist" in msg):
        return f"AI model not found. Check DEFAULT_CHATBOT_MODEL or INTERNAL_MODEL in your .env. Detail: {exc}"
    return f"AI configuration failed: {exc}"


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

        await clear_chatbot_setup_state(str(chatbot.workspace_id), str(chatbot_id))
        await emit_to_workspace(str(chatbot.workspace_id), "chatbot:status_changed", {
            "chatbot_id": str(chatbot_id),
            "setup_status": "ready",
        })


async def _mark_setup_failed(chatbot_id: uuid.UUID, reason: str = "") -> None:
    await engine.dispose()
    from app.models.knowledge import Chatbot

    async with async_session_factory() as session:
        result = await session.execute(select(Chatbot).where(Chatbot.id == chatbot_id))
        chatbot = result.scalar_one_or_none()
        if chatbot and chatbot.setup_status == "configuring":
            chatbot.setup_status = "setup_failed"
            chatbot.setup_error = reason
            await session.commit()

            await clear_chatbot_setup_state(str(chatbot.workspace_id), str(chatbot_id))
            await emit_to_workspace(str(chatbot.workspace_id), "chatbot:status_changed", {
                "chatbot_id": str(chatbot_id),
                "setup_status": "setup_failed",
                "setup_error": reason,
            })
