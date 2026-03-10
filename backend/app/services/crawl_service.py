# backend/app/services/crawl_service.py
import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import CrawlJob, Document, KnowledgeBase
from app.services.crawler import discover_urls
from app.services.fetcher import FetchResult, fetch

logger = logging.getLogger(__name__)

_FETCH_CONCURRENCY = 5  # max parallel HTTP fetches


@dataclass
class CrawlStartResult:
    job_id: str
    kb_id: str
    pages_discovered: int
    pages_queued: int
    over_limit: bool
    limit: int


async def start_crawl(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    url: str,
    max_pages: int,
    kb_id: uuid.UUID | None = None,
) -> CrawlStartResult:
    from app.workers.tasks.ingest_document import ingest_document

    # 1. Discover URLs
    crawl_result = await discover_urls(url, max_pages)

    # 2. Create KB if not provided
    if kb_id is None:
        domain = urlparse(url).netloc
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        kb = KnowledgeBase(workspace_id=workspace_id, name=f"{domain} — crawled {date_str}")
        db.add(kb)
        await db.flush()
        kb_id = kb.id
    else:
        r = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.workspace_id == workspace_id,
            )
        )
        if r.scalar_one_or_none() is None:
            raise ValueError(f"Knowledge base {kb_id} not found")

    # 3. Create CrawlJob and COMMIT before queuing tasks
    job = CrawlJob(
        workspace_id=workspace_id,
        kb_id=kb_id,
        root_url=url,
        status="pending",
        pages_discovered=crawl_result.total_discovered,
        max_pages=max_pages,
        over_limit=crawl_result.over_limit,
    )
    db.add(job)
    await db.flush()
    await db.commit()       # Celery workers need to read this row
    await db.refresh(job)   # re-attach expired object after commit (required for async sessions)

    # 4. Fetch all URLs concurrently with bounded parallelism
    semaphore = asyncio.Semaphore(_FETCH_CONCURRENCY)

    async def _fetch_one(page_url: str) -> FetchResult:
        async with semaphore:
            return await fetch(page_url)

    fetch_results = await asyncio.gather(
        *[_fetch_one(u) for u in crawl_result.urls],
        return_exceptions=True,
    )

    # 5. Create Documents and queue ingestion
    pages_queued = 0
    pages_failed = 0

    for page_url, result in zip(crawl_result.urls, fetch_results):
        if isinstance(result, Exception):
            logger.warning("Fetch exception %s: %s", page_url, result)
            pages_failed += 1
            continue
        if result.status_code >= 400 or not result.text:
            logger.warning("Skipping %s (status=%d)", page_url, result.status_code)
            pages_failed += 1
            continue

        doc = Document(
            workspace_id=workspace_id,
            knowledge_base_id=kb_id,
            source_type="text",       # pre-fetched; pipeline reads raw_content directly
            source_url=page_url,
            raw_content=result.text,
            title=result.title,
            status="pending",
        )
        db.add(doc)
        await db.flush()
        ingest_document.delay(str(doc.id))
        pages_queued += 1

    # 6. Update CrawlJob
    job.pages_queued = pages_queued
    job.pages_failed = pages_failed
    job.status = "running"
    await db.commit()

    return CrawlStartResult(
        job_id=str(job.id),
        kb_id=str(kb_id),
        pages_discovered=crawl_result.total_discovered,
        pages_queued=pages_queued,
        over_limit=crawl_result.over_limit,
        limit=max_pages,
    )
