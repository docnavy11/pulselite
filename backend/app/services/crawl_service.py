import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Chatbot, CrawlJob, Document, KnowledgeBase
from app.realtime.events import notify_workspace
from app.services.crawler import DiscoveredUrl, discover_urls
from app.services.fetcher import fetch


# Compatibility shims — old Redis state functions replaced by SSE push
async def emit_to_workspace(workspace_id, event, data):
    await notify_workspace(workspace_id, event, data)


async def write_chatbot_setup_state(*args, **kwargs):
    pass


async def write_crawl_state(*args, **kwargs):
    pass


async def clear_crawl_state(*args, **kwargs):
    pass


logger = logging.getLogger(__name__)

_FETCH_CONCURRENCY = 30


@dataclass
class CrawlStartResult:
    job_id: str
    kb_id: str
    pages_discovered: int
    pages_queued: int


async def prepare_crawl(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    url: str,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
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
        include_paths=include_paths or [],
        exclude_paths=exclude_paths or [],
    )
    db.add(job)
    await db.flush()

    # If this crawl is for a chatbot wizard, mark the chatbot as setting up
    if chatbot_id is not None:
        chatbot_result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id))
        chatbot = chatbot_result.scalar_one_or_none()
        if chatbot is not None:
            chatbot.setup_status = "crawling"
            chatbot.active_crawl_job_id = job.id

    await db.commit()

    # Emit chatbot status change + persist state
    if chatbot_id is not None:
        await write_chatbot_setup_state(str(workspace_id), str(chatbot_id), "crawling")
        await emit_to_workspace(
            str(workspace_id),
            "chatbot:status_changed",
            {
                "chatbot_id": str(chatbot_id),
                "setup_status": "crawling",
            },
        )

    return str(job.id), str(kb_id)


async def execute_crawl(db: AsyncSession, job_id: uuid.UUID) -> None:
    """Discover URLs, fetch each page, create Documents, fire ingest tasks.
    Updates CrawlJob.phase and CrawlJob.error_message at each transition so
    the polling endpoint gives the frontend real-time visibility."""
    from app.background.runner import submit_job

    r = await db.execute(select(CrawlJob).where(CrawlJob.id == job_id))
    job = r.scalar_one()

    job.started_at = datetime.now(timezone.utc)
    job.status = "running"
    job.phase = "discovering"
    await db.commit()
    await db.refresh(job)

    # Resolve chatbot_id from KB (CrawlJob does not have chatbot_id)
    _kb_result = await db.execute(select(KnowledgeBase.chatbot_id).where(KnowledgeBase.id == job.kb_id))
    _kb_row = _kb_result.one_or_none()
    _chatbot_id = str(_kb_row.chatbot_id) if _kb_row and _kb_row.chatbot_id else None

    _crawl_state = {
        "chatbot_id": _chatbot_id,
        "phase": "discovering",
        "pages_discovered": 0,
        "pages_queued": 0,
        "pages_failed": 0,
        "status": "running",
    }
    await write_crawl_state(str(job.workspace_id), str(job.id), _crawl_state)
    await emit_to_workspace(
        str(job.workspace_id),
        "crawl:progress",
        {
            "job_id": str(job.id),
            **_crawl_state,
        },
    )

    # Phase 1: discover URLs — wrap so any error is stored and surfaced immediately
    try:
        urls = await discover_urls(
            job.root_url,
            include_paths=job.include_paths or None,
            exclude_paths=job.exclude_paths or None,
        )
    except Exception as exc:
        logger.error("URL discovery failed for job %s: %s", job_id, exc)
        job.status = "failed"
        job.phase = None
        job.error_message = f"Could not discover pages: {exc}"
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await clear_crawl_state(str(job.workspace_id), str(job.id))
        await emit_to_workspace(
            str(job.workspace_id),
            "crawl:completed",
            {
                "job_id": str(job.id),
                "chatbot_id": _chatbot_id,
                "status": "failed",
                "pages_queued": 0,
                "pages_failed": 0,
                "error_message": job.error_message,
            },
        )
        return

    if not urls:
        job.status = "failed"
        job.phase = None
        job.error_message = (
            "No pages found on this site. Check that the URL is correct and the site is publicly accessible."
        )
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await clear_crawl_state(str(job.workspace_id), str(job.id))
        await emit_to_workspace(
            str(job.workspace_id),
            "crawl:completed",
            {
                "job_id": str(job.id),
                "chatbot_id": _chatbot_id,
                "status": "failed",
                "pages_queued": 0,
                "pages_failed": 0,
                "error_message": job.error_message,
            },
        )
        return

    job.pages_discovered = len(urls)
    job.phase = "fetching"
    await db.commit()
    await db.refresh(job)

    _crawl_state = {
        "chatbot_id": _chatbot_id,
        "phase": "fetching",
        "pages_discovered": job.pages_discovered,
        "pages_queued": 0,
        "pages_failed": 0,
        "status": "running",
    }
    await write_crawl_state(str(job.workspace_id), str(job.id), _crawl_state)
    await emit_to_workspace(
        str(job.workspace_id),
        "crawl:progress",
        {
            "job_id": str(job.id),
            **_crawl_state,
        },
    )

    # Phase 2: fetch pages concurrently (with live DB progress updates).
    # AsyncSession is not concurrency-safe, so fetches run concurrently but
    # DB writes happen one at a time via asyncio.as_completed.
    semaphore = asyncio.Semaphore(_FETCH_CONCURRENCY)
    _MAX_RETRIES = 3

    @dataclass
    class _FetchResult:
        url: str
        text: str
        title: str
        failed: bool
        error: str = ""

    async def _fetch(discovered: DiscoveredUrl) -> _FetchResult:
        # Reuse content already fetched during BFS discovery (avoids double Playwright launch)
        if discovered.prefetched_text is not None:
            return _FetchResult(
                url=discovered.url,
                text=discovered.prefetched_text,
                title=discovered.prefetched_title or "",
                failed=False,
            )

        page_url = discovered.url
        for attempt in range(_MAX_RETRIES + 1):
            async with semaphore:
                try:
                    result = await fetch(page_url)
                except Exception as exc:
                    logger.warning("Fetch exception %s: %s", page_url, exc)
                    return _FetchResult(url=page_url, text="", title="", failed=True, error=str(exc))

            if result.status_code == 429:
                if attempt < _MAX_RETRIES:
                    wait = min(5 * (2**attempt), 60)
                    logger.warning(
                        "Rate limited on %s, retrying in %ds (attempt %d/%d)",
                        page_url,
                        wait,
                        attempt + 1,
                        _MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    continue
                return _FetchResult(
                    url=page_url,
                    text="",
                    title="",
                    failed=True,
                    error="HTTP 429 (rate limited, max retries exceeded)",
                )

            if result.status_code >= 400:
                logger.warning("Skipping %s (status=%d)", page_url, result.status_code)
                return _FetchResult(url=page_url, text="", title="", failed=True, error=f"HTTP {result.status_code}")
            if result.text == "":
                return _FetchResult(url=page_url, text="", title="", failed=True, error="Empty response")
            return _FetchResult(url=page_url, text=result.text, title=result.title or "", failed=False)

        return _FetchResult(url=page_url, text="", title="", failed=True, error="HTTP 429 (rate limited)")

    # Write to DB as each fetch completes — gives live pages_queued progress
    import time as _time

    _last_progress_emit = 0.0
    doc_ids: list[str] = []
    fetch_tasks = [asyncio.create_task(_fetch(d)) for d in urls]

    try:
        for coro in asyncio.as_completed(fetch_tasks):
            fr = await coro
            if fr.failed:
                failed_doc = Document(
                    workspace_id=job.workspace_id,
                    knowledge_base_id=job.kb_id,
                    source_type="url",
                    source_url=fr.url,
                    title=fr.url,
                    status="failed",
                    metadata_={"error": fr.error},
                )
                db.add(failed_doc)
                await db.flush()
                await db.execute(
                    update(CrawlJob).where(CrawlJob.id == job_id).values(pages_failed=CrawlJob.pages_failed + 1)
                )
                await db.commit()
                await db.refresh(job)

                # Debounced progress emit
                now = _time.monotonic()
                if now - _last_progress_emit >= 1.0:
                    _last_progress_emit = now
                    _crawl_state = {
                        "chatbot_id": _chatbot_id,
                        "phase": "fetching",
                        "pages_discovered": job.pages_discovered,
                        "pages_queued": job.pages_queued,
                        "pages_failed": job.pages_failed,
                        "status": "running",
                    }
                    await write_crawl_state(str(job.workspace_id), str(job.id), _crawl_state)
                    await emit_to_workspace(
                        str(job.workspace_id),
                        "crawl:progress",
                        {
                            "job_id": str(job.id),
                            **_crawl_state,
                        },
                    )
                continue

            doc = Document(
                workspace_id=job.workspace_id,
                knowledge_base_id=job.kb_id,
                source_type="text",
                source_url=fr.url,
                raw_content=fr.text,
                title=fr.title,
                status="pending",
            )
            db.add(doc)
            await db.flush()
            doc_ids.append(str(doc.id))
            await db.execute(
                update(CrawlJob).where(CrawlJob.id == job_id).values(pages_queued=CrawlJob.pages_queued + 1)
            )
            await db.commit()
            await db.refresh(job)

            # Debounced progress emit (at most every 1s)
            now = _time.monotonic()
            if now - _last_progress_emit >= 1.0:
                _last_progress_emit = now
                _crawl_state = {
                    "chatbot_id": _chatbot_id,
                    "phase": "fetching",
                    "pages_discovered": job.pages_discovered,
                    "pages_queued": job.pages_queued,
                    "pages_failed": job.pages_failed,
                    "status": "running",
                }
                await write_crawl_state(str(job.workspace_id), str(job.id), _crawl_state)
                await emit_to_workspace(
                    str(job.workspace_id),
                    "crawl:progress",
                    {
                        "job_id": str(job.id),
                        **_crawl_state,
                    },
                )
    except Exception:
        for task in fetch_tasks:
            task.cancel()
        raise

    # Check if any pages were successfully fetched
    if not doc_ids and job.pages_failed == len(urls):
        job.status = "failed"
        job.phase = None
        job.error_message = "All pages failed to fetch. The site may be blocking crawlers or requiring authentication."
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await clear_crawl_state(str(job.workspace_id), str(job.id))
        await emit_to_workspace(
            str(job.workspace_id),
            "crawl:completed",
            {
                "job_id": str(job.id),
                "chatbot_id": _chatbot_id,
                "status": "failed",
                "pages_queued": 0,
                "pages_failed": len(urls),
                "error_message": job.error_message,
            },
        )
        return

    # Fire ingest tasks — all docs committed, workers can read them
    for doc_id in doc_ids:
        await submit_job("ingest_document", {"document_id": doc_id})

    # Mark job as completed
    job.status = "completed"
    job.phase = None
    job.completed_at = datetime.now(timezone.utc)
    await db.commit()

    await clear_crawl_state(str(job.workspace_id), str(job.id))
    await emit_to_workspace(
        str(job.workspace_id),
        "crawl:completed",
        {
            "job_id": str(job.id),
            "chatbot_id": _chatbot_id,
            "status": "completed",
            "pages_queued": len(doc_ids),
            "pages_failed": job.pages_failed,
            "error_message": None,
        },
    )
