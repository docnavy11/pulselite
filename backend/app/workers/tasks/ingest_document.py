import asyncio
import uuid

from app.database import async_session_factory, engine
from app.services.ingestion.pipeline import run_ingestion
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def ingest_document(self, document_id: str) -> dict:
    try:
        result = asyncio.run(_run(uuid.UUID(document_id)))
        return result
    except Exception as exc:
        self.retry(exc=exc)


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
        except Exception:
            await session.rollback()
            raise
