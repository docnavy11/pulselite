import asyncio
import logging
import uuid

from celery.exceptions import MaxRetriesExceededError

from app.database import async_session_factory, engine
from app.services.ingestion.pipeline import run_ingestion
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Lazy reference — Task 5 (run_autoconfig) may not exist yet during development.
# Tests patch this module-level name directly.
try:
    from app.workers.tasks.run_autoconfig import run_autoconfig_for_chatbot
except ImportError:  # pragma: no cover
    run_autoconfig_for_chatbot = None  # type: ignore[assignment]


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def ingest_document(self, document_id: str) -> dict:
    try:
        result = asyncio.run(_run(uuid.UUID(document_id)))
        return result
    except MaxRetriesExceededError:
        # All retries exhausted — mark document as failed so it's visible in the UI
        asyncio.run(_mark_document_failed(uuid.UUID(document_id), "Max retries exceeded"))
        return {"status": "failed", "document_id": document_id}
    except Exception as exc:
        raise self.retry(exc=exc)


async def _run(document_id: uuid.UUID) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        # Idempotency guard: if already processed, skip re-ingestion
        from app.models.knowledge import Document
        from sqlalchemy import select as sa_select
        doc_check = await session.execute(sa_select(Document).where(Document.id == document_id))
        doc = doc_check.scalar_one_or_none()
        if doc is not None and doc.status in ("indexed", "skipped"):
            # Still run completion check — this may be a re-delivered task for the last doc
            await _check_and_trigger_autoconfig(document_id)
            return {"status": "already_processed", "document_id": str(document_id)}

        try:
            await run_ingestion(session, document_id)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            await _mark_document_failed(document_id, str(exc))
            raise

    # Completion check runs outside the ingestion session (after commit)
    await _check_and_trigger_autoconfig(document_id)
    return {"status": "success", "document_id": str(document_id)}


async def _mark_document_failed(document_id: uuid.UUID, reason: str) -> None:
    from app.models.knowledge import Document
    from sqlalchemy import select

    await engine.dispose()
    async with async_session_factory() as session:
        try:
            result = await session.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc and doc.status not in ("indexed", "skipped", "failed"):
                doc.status = "failed"
                doc.error_message = reason
                await session.commit()
        except Exception as e:
            logger.error("Failed to mark document %s as failed: %s", document_id, e)

    # Check completion even after marking failed — this doc may be the last one
    await _check_and_trigger_autoconfig(document_id)


async def _check_and_trigger_autoconfig(document_id: uuid.UUID) -> None:
    """If all documents in the KB are terminal, atomically claim the configuring
    transition and fire run_autoconfig_for_chatbot. Called after both success and
    failure ingestion paths."""
    from sqlalchemy import func, select, update
    from app.models.knowledge import Chatbot, Document, KnowledgeBase

    await engine.dispose()
    async with async_session_factory() as session:
        # Step 1: Find the KB for this document
        doc_result = await session.execute(
            select(Document.knowledge_base_id).where(Document.id == document_id)
        )
        doc_row = doc_result.one_or_none()
        if doc_row is None:
            return
        kb_id = doc_row.knowledge_base_id

        # Step 2: Find the chatbot that owns this KB (nullable FK)
        kb_result = await session.execute(
            select(KnowledgeBase.chatbot_id).where(KnowledgeBase.id == kb_id)
        )
        kb_row = kb_result.one_or_none()
        if kb_row is None or kb_row.chatbot_id is None:
            return
        chatbot_id = kb_row.chatbot_id

        # Step 3: Check if any docs are still in progress
        pending_result = await session.execute(
            select(func.count()).where(
                Document.knowledge_base_id == kb_id,
                Document.status.in_(["pending", "processing"]),
            )
        )
        pending_count = pending_result.scalar_one()
        if pending_count > 0:
            return

        # Step 4: Atomic claim — only the winner fires autoconfig
        update_result = await session.execute(
            update(Chatbot)
            .where(Chatbot.id == chatbot_id, Chatbot.setup_status == "crawling")
            .values(setup_status="configuring")
            .returning(Chatbot.id)
        )
        await session.commit()

        if update_result.scalar_one_or_none() is not None:
            run_autoconfig_for_chatbot.delay(str(chatbot_id))
