# backend/app/workers/tasks/crawl_website.py
import asyncio
import logging
import uuid

from app.database import async_session_factory, engine
from app.services.realtime import clear_crawl_state
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, soft_time_limit=540, time_limit=600)
def crawl_website(self, job_id: str) -> dict:
    try:
        asyncio.run(_run(uuid.UUID(job_id)))
        return {"status": "ok", "job_id": job_id}
    except Exception as exc:
        raise self.retry(exc=exc)


async def _run(job_id: uuid.UUID) -> None:
    from app.services.crawl_service import execute_crawl

    await engine.dispose()
    async with async_session_factory() as session:
        try:
            await execute_crawl(session, job_id)
        except Exception as exc:
            await session.rollback()
            await _mark_job_failed(str(job_id), error_message=f"Unexpected error: {exc}")
            raise


async def _mark_job_failed(job_id: str, error_message: str | None = None) -> None:
    from app.models.knowledge import CrawlJob
    from datetime import datetime, timezone
    from sqlalchemy import select

    await engine.dispose()
    async with async_session_factory() as session:
        try:
            result = await session.execute(select(CrawlJob).where(CrawlJob.id == uuid.UUID(job_id)))
            job = result.scalar_one_or_none()
            if job:
                job.status = "failed"
                job.phase = None
                if error_message:
                    job.error_message = error_message
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()
                await clear_crawl_state(str(job.workspace_id), job_id)
        except Exception as e:
            logger.error("Failed to mark crawl job %s as failed: %s", job_id, e)
