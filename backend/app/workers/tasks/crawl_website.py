# backend/app/workers/tasks/crawl_website.py
import asyncio
import uuid

from app.database import async_session_factory, engine
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_website(
    self,
    workspace_id: str,
    url: str,
    max_pages: int,
    kb_id: str | None = None,
) -> dict:
    try:
        result = asyncio.run(
            _run(uuid.UUID(workspace_id), url, max_pages, uuid.UUID(kb_id) if kb_id else None)
        )
        return result
    except Exception as exc:
        self.retry(exc=exc)


async def _run(
    workspace_id: uuid.UUID,
    url: str,
    max_pages: int,
    kb_id: uuid.UUID | None,
) -> dict:
    from app.services.crawl_service import start_crawl

    # Dispose stale pool connections from prior event loop (asyncio.run creates a fresh loop)
    await engine.dispose()
    async with async_session_factory() as session:
        try:
            result = await start_crawl(session, workspace_id, url, max_pages, kb_id)
            # start_crawl commits internally and sets CrawlJob.status="running".
            # Individual pages are dispatched as ingest_document child tasks that run
            # asynchronously — the job stays "running" until ingestion completes.
            return {
                "status": "running",
                "job_id": result.job_id,
                "kb_id": result.kb_id,
                "pages_discovered": result.pages_discovered,
                "pages_queued": result.pages_queued,
                "over_limit": result.over_limit,
            }
        except Exception:
            await session.rollback()
            raise
