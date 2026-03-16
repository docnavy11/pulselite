import asyncio
import logging
from collections import defaultdict

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select

from app.database import async_session_factory, engine
from app.models.knowledge import Document
from app.services.realtime import emit_task_event
from app.workers.celery_app import celery_app
from app.workers.tasks.ingest_document import ingest_document

from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, soft_time_limit=170, time_limit=180)
def sync_stale_documents(self) -> dict:
    try:
        result = asyncio.run(_find_and_queue_stale(self.request.id))
        return result
    except MaxRetriesExceededError:
        logger.error("sync_stale_documents failed after max retries")
        return {"status": "failed", "reason": "max retries exceeded"}
    except Exception as exc:
        raise self.retry(exc=exc)


async def _find_and_queue_stale(task_id: str) -> dict:
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

        # Group by workspace for per-workspace event emission
        by_ws: dict[str, list] = defaultdict(list)
        for doc in documents:
            doc.status = "stale"
            by_ws[str(doc.workspace_id)].append(str(doc.id))

        await session.commit()  # commit first

        queued = 0
        for ws_id, doc_ids in by_ws.items():
            await emit_task_event(ws_id, "started", "sync_documents", task_id,
                                  detail=f"Syncing {len(doc_ids)} documents")
            for doc_id in doc_ids:
                ingest_document.delay(doc_id)
                queued += 1
            await emit_task_event(ws_id, "completed", "sync_documents", task_id,
                                  detail=f"Queued {len(doc_ids)} documents")

        return {"queued": queued}
