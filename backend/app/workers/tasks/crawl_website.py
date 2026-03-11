# backend/app/workers/tasks/crawl_website.py
import asyncio
import logging
import uuid

from app.database import async_session_factory, engine
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_website(self, job_id: str) -> dict:
    try:
        asyncio.run(_run(uuid.UUID(job_id)))
        return {"status": "ok", "job_id": job_id}
    except Exception as exc:
        raise self.retry(exc=exc)


async def _run(job_id: uuid.UUID) -> None:
    from app.models.knowledge import CrawlJob
    from app.services.crawl_service import execute_crawl
    from sqlalchemy import select

    await engine.dispose()
    async with async_session_factory() as session:
        job_id_str = str(job_id)
        try:
            await execute_crawl(session, job_id)
        except Exception:
            await session.rollback()
            await _mark_job_failed(job_id_str)
            raise


async def _mark_job_failed(job_id: str) -> None:
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
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()
        except Exception as e:
            logger.error("Failed to mark crawl job %s as failed: %s", job_id, e)
