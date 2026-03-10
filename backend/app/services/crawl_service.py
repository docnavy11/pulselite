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
from app.services.fetcher import fetch

logger = logging.getLogger(__name__)

_FETCH_CONCURRENCY = 5


@dataclass
class CrawlStartResult:
    job_id: str
    kb_id: str
    pages_discovered: int
    pages_queued: int
    over_limit: bool
    limit: int


async def prepare_crawl(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    url: str,
    max_pages: int,
    kb_id: uuid.UUID | None = None,
    chatbot_id: uuid.UUID | None = None,
) -> tuple[str, str]:
    """Create KB + CrawlJob and commit immediately. Returns (job_id, kb_id).
    Does NOT fetch any pages — that happens in the Celery task."""

    parsed_root = urlparse(url)
    if parsed_root.scheme not in ("http", "https"):
        raise ValueError("URL must be http or https")

    if kb_id is None:
        domain = urlparse(url).netloc
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        kb = KnowledgeBase(
            workspace_id=workspace_id,
            name=f"{domain} — crawled {date_str}",
            chatbot_id=chatbot_id,
        )
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

    job = CrawlJob(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        kb_id=kb_id,
        root_url=url,
        status="pending",
        pages_discovered=0,
        max_pages=max_pages,
        over_limit=False,
    )
    db.add(job)
    await db.flush()
    await db.commit()
    return str(job.id), str(kb_id)


async def execute_crawl(db: AsyncSession, job_id: uuid.UUID) -> None:
    """Discover URLs, fetch each page, create Documents, fire ingest tasks.
    Updates CrawlJob.pages_queued after every successfully fetched page so
    the polling endpoint reflects live progress."""
    from app.workers.tasks.ingest_document import ingest_document

    r = await db.execute(select(CrawlJob).where(CrawlJob.id == job_id))
    job = r.scalar_one()

    job.started_at = datetime.now(timezone.utc)
    job.status = "running"
    await db.commit()
    await db.refresh(job)

    # Phase 1: discover URLs
    crawl_result = await discover_urls(job.root_url, job.max_pages)
    job.pages_discovered = crawl_result.total_discovered
    job.over_limit = crawl_result.over_limit
    await db.commit()
    await db.refresh(job)

    # Phase 2: fetch + create Document for each URL, update progress per page
    semaphore = asyncio.Semaphore(_FETCH_CONCURRENCY)
    doc_ids: list[str] = []

    async def _fetch_and_store(page_url: str) -> None:
        async with semaphore:
            try:
                result = await fetch(page_url)
            except Exception as exc:
                logger.warning("Fetch exception %s: %s", page_url, exc)
                job.pages_failed = (job.pages_failed or 0) + 1
                await db.commit()
                return

            if result.status_code >= 400 or result.text == "":
                logger.warning("Skipping %s (status=%d)", page_url, result.status_code)
                job.pages_failed = (job.pages_failed or 0) + 1
                await db.commit()
                return

            doc = Document(
                workspace_id=job.workspace_id,
                knowledge_base_id=job.kb_id,
                source_type="text",
                source_url=page_url,
                raw_content=result.text,
                title=result.title,
                status="pending",
            )
            db.add(doc)
            await db.flush()
            doc_ids.append(str(doc.id))
            job.pages_queued = (job.pages_queued or 0) + 1
            await db.commit()

    await asyncio.gather(*[_fetch_and_store(u) for u in crawl_result.urls])

    # Fire ingest tasks — all docs committed, workers can read them
    for doc_id in doc_ids:
        ingest_document.delay(doc_id)


# ---------------------------------------------------------------------------
# Legacy synchronous entry point (kept for backward compatibility / tests)
# ---------------------------------------------------------------------------

async def start_crawl(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    url: str,
    max_pages: int,
    kb_id: uuid.UUID | None = None,
    chatbot_id: uuid.UUID | None = None,
) -> CrawlStartResult:
    job_id_str, kb_id_str = await prepare_crawl(db, workspace_id, url, max_pages, kb_id, chatbot_id)
    await execute_crawl(db, uuid.UUID(job_id_str))

    r = await db.execute(select(CrawlJob).where(CrawlJob.id == uuid.UUID(job_id_str)))
    job = r.scalar_one()
    return CrawlStartResult(
        job_id=job_id_str,
        kb_id=kb_id_str,
        pages_discovered=job.pages_discovered,
        pages_queued=job.pages_queued,
        over_limit=job.over_limit,
        limit=max_pages,
    )
