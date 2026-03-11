import asyncio
import logging
import uuid

from celery.exceptions import MaxRetriesExceededError

from app.database import async_session_factory, engine
from app.services.ingestion.pipeline import run_ingestion
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


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
    # Dispose stale pool connections from any previous event loop before opening a session.
    # Each asyncio.run() creates a fresh loop; connections held by the pool are tied to
    # the old (now closed) loop and will raise "Future attached to a different loop".
    await engine.dispose()
    async with async_session_factory() as session:
        try:
            await run_ingestion(session, document_id)
            await session.commit()
            return {"status": "success", "document_id": str(document_id)}
        except Exception as exc:
            await session.rollback()
            # Persist the failed status in a fresh session so retries don't hide the failure
            await _mark_document_failed(document_id, str(exc))
            raise


async def _mark_document_failed(document_id: uuid.UUID, reason: str) -> None:
    from app.models.knowledge import Document
    from sqlalchemy import select

    await engine.dispose()
    async with async_session_factory() as session:
        try:
            result = await session.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc and doc.status != "indexed":
                doc.status = "failed"
                await session.commit()
        except Exception as e:
            logger.error("Failed to mark document %s as failed: %s", document_id, e)
