import asyncio

from sqlalchemy import select

from app.database import async_session_factory, engine
from app.models.knowledge import Document
from app.workers.celery_app import celery_app
from app.workers.tasks.ingest_document import ingest_document

from datetime import datetime, timezone


@celery_app.task
def sync_stale_documents() -> dict:
    result = asyncio.run(_find_and_queue_stale())
    return result


async def _find_and_queue_stale() -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(Document).where(
                Document.next_sync_at <= now,
                Document.status.in_(["indexed", "stale"]),
                Document.sync_frequency != "manual",
            )
        )
        documents = result.scalars().all()

        doc_ids = []
        queued = 0
        for doc in documents:
            doc.status = "stale"
            doc_ids.append(str(doc.id))
            queued += 1

        await session.commit()  # commit first

        for doc_id in doc_ids:
            ingest_document.delay(doc_id)  # then fire tasks

        return {"queued": queued}
