# backend/app/workers/tasks/crawl_website.py
import asyncio
import uuid
from datetime import datetime, timezone

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
        raise self.retry(exc=exc)


async def _run(
    workspace_id: uuid.UUID,
    url: str,
    max_pages: int,
    kb_id: uuid.UUID | None,
) -> dict:
    from app.models.knowledge import CrawlJob
    from app.services.crawl_service import start_crawl
    from sqlalchemy import select

    # Dispose stale pool connections from prior event loop (asyncio.run creates a fresh loop)
    await engine.dispose()
    async with async_session_factory() as session:
        job_id: str | None = None
        try:
            result = await start_crawl(session, workspace_id, url, max_pages, kb_id)
            job_id = result.job_id

            # Set started_at now that the job exists and we have its ID
            job_q = await session.execute(select(CrawlJob).where(CrawlJob.id == uuid.UUID(job_id)))
            job = job_q.scalar_one_or_none()
            if job:
                job.started_at = datetime.now(timezone.utc)
                await session.commit()

            # start_crawl sets status="running" and dispatches ingest_document child tasks.
            # Job completion is tracked per-document; we do NOT set status="completed" here.
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
            # Mark job as failed if it was created before the exception occurred
            if job_id:
                await _mark_job_failed(job_id)
            raise


async def _mark_job_failed(job_id: str) -> None:
    """Update CrawlJob status to 'failed' using a fresh session (original session rolled back)."""
    from app.models.knowledge import CrawlJob
    from sqlalchemy import select

    async with async_session_factory() as session:
        try:
            result = await session.execute(select(CrawlJob).where(CrawlJob.id == uuid.UUID(job_id)))
            job = result.scalar_one_or_none()
            if job:
                job.status = "failed"
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()
        except Exception:
            pass  # best-effort; don't mask the original exception
