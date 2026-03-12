# backend/app/api/v1/crawl.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace
from app.models.knowledge import CrawlJob, Document
from app.schemas.crawl import CrawlJobStatusResponse, CrawlJobSummary, CrawlRequest, CrawlResponse
from app.services.crawl_service import prepare_crawl
from app.workers.tasks.crawl_website import crawl_website

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["crawl"])


@router.post("/crawl", response_model=CrawlResponse, status_code=201)
async def crawl_website_endpoint(
    body: CrawlRequest,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    try:
        job_id, kb_id = await prepare_crawl(
            db,
            workspace_id=workspace_id,
            url=body.url,
            include_paths=body.include_paths or None,
            exclude_paths=body.exclude_paths or None,
            kb_id=body.knowledge_base_id,
            chatbot_id=body.chatbot_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    crawl_website.delay(job_id)

    return CrawlResponse(
        job_id=job_id,
        kb_id=kb_id,
        pages_discovered=0,
        pages_queued=0,
    )


@router.get("/crawl", response_model=CrawlJobStatusResponse | None)
async def get_latest_crawl_for_chatbot(
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent crawl job for a chatbot's knowledge base."""
    from app.models.knowledge import KnowledgeBase

    kb_result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.workspace_id == workspace_id,
            KnowledgeBase.chatbot_id == chatbot_id,
        )
    )
    kb = kb_result.scalar_one_or_none()
    if not kb:
        return None

    job_result = await db.execute(
        select(CrawlJob)
        .where(CrawlJob.kb_id == kb.id)
        .order_by(CrawlJob.created_at.desc())
        .limit(1)
    )
    job = job_result.scalar_one_or_none()
    if not job:
        return None

    from datetime import datetime, timezone

    docs_total_result = await db.execute(
        select(func.count(Document.id)).where(Document.knowledge_base_id == job.kb_id)
    )
    docs_indexed_result = await db.execute(
        select(func.count(Document.id)).where(
            Document.knowledge_base_id == job.kb_id,
            Document.status == "indexed",
        )
    )
    docs_failed_result = await db.execute(
        select(func.count(Document.id)).where(
            Document.knowledge_base_id == job.kb_id,
            Document.status == "failed",
        )
    )
    docs_total = docs_total_result.scalar() or 0
    docs_indexed = docs_indexed_result.scalar() or 0
    docs_failed = docs_failed_result.scalar() or 0

    docs_skipped_result = await db.execute(
        select(func.count()).select_from(Document).where(
            Document.knowledge_base_id == job.kb_id,
            Document.status == "skipped",
        )
    )
    docs_skipped = docs_skipped_result.scalar() or 0

    stalled = False
    if job.status in ("running", "pending") and job.started_at:
        elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
        stalled = elapsed > 900

    return CrawlJobStatusResponse(
        job_id=str(job.id),
        kb_id=str(job.kb_id),
        status=job.status,
        pages_discovered=job.pages_discovered,
        pages_queued=job.pages_queued,
        pages_failed=job.pages_failed,
        docs_indexed=docs_indexed,
        docs_total=docs_total,
        docs_failed=docs_failed,
        docs_skipped=docs_skipped,
        stalled=stalled,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        phase=job.phase,
        error_message=job.error_message,
    )


@router.get("/crawl/history", response_model=list[CrawlJobSummary])
async def list_crawl_history(
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Return all crawl jobs for a chatbot, newest first."""
    from app.models.knowledge import KnowledgeBase

    kb_result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.workspace_id == workspace_id,
            KnowledgeBase.chatbot_id == chatbot_id,
        )
    )
    kb = kb_result.scalar_one_or_none()
    if not kb:
        return []

    jobs_result = await db.execute(
        select(CrawlJob)
        .where(CrawlJob.kb_id == kb.id)
        .order_by(CrawlJob.created_at.desc())
        .limit(20)
    )
    jobs = jobs_result.scalars().all()

    # Fetch indexed doc counts per kb in one query
    kb_indexed = {}
    if jobs:
        indexed_result = await db.execute(
            select(Document.knowledge_base_id, func.count(Document.id))
            .where(
                Document.knowledge_base_id == kb.id,
                Document.status == "indexed",
            )
            .group_by(Document.knowledge_base_id)
        )
        for kb_id, cnt in indexed_result:
            kb_indexed[str(kb_id)] = cnt

    # Get skipped counts for all returned jobs in one query
    skipped_counts: dict[str, int] = {}
    if jobs:
        skipped_result = await db.execute(
            select(Document.knowledge_base_id, func.count().label("cnt"))
            .where(Document.knowledge_base_id.in_([job.kb_id for job in jobs]))
            .where(Document.status == "skipped")
            .group_by(Document.knowledge_base_id)
        )
        kb_skipped = {str(row.knowledge_base_id): row.cnt for row in skipped_result}
        skipped_counts = {str(job.id): kb_skipped.get(str(job.kb_id), 0) for job in jobs}

    return [
        CrawlJobSummary(
            job_id=str(j.id),
            status=j.status,
            root_url=j.root_url,
            pages_discovered=j.pages_discovered,
            pages_queued=j.pages_queued,
            pages_failed=j.pages_failed,
            docs_indexed=kb_indexed.get(str(j.kb_id), 0),
            docs_skipped=skipped_counts.get(str(j.id), 0),
            created_at=j.created_at.isoformat(),
            completed_at=j.completed_at.isoformat() if j.completed_at else None,
            phase=j.phase,
            error_message=j.error_message,
        )
        for j in jobs
    ]


@router.get("/crawl/{job_id}", response_model=CrawlJobStatusResponse)
async def get_crawl_status(
    job_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CrawlJob).where(CrawlJob.id == job_id, CrawlJob.workspace_id == workspace_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found")

    from datetime import datetime, timezone

    docs_total_result = await db.execute(
        select(func.count(Document.id)).where(Document.knowledge_base_id == job.kb_id)
    )
    docs_indexed_result = await db.execute(
        select(func.count(Document.id)).where(
            Document.knowledge_base_id == job.kb_id,
            Document.status == "indexed",
        )
    )
    docs_failed_result = await db.execute(
        select(func.count(Document.id)).where(
            Document.knowledge_base_id == job.kb_id,
            Document.status == "failed",
        )
    )
    docs_total = docs_total_result.scalar() or 0
    docs_indexed = docs_indexed_result.scalar() or 0
    docs_failed = docs_failed_result.scalar() or 0

    docs_skipped_result = await db.execute(
        select(func.count()).select_from(Document).where(
            Document.knowledge_base_id == job.kb_id,
            Document.status == "skipped",
        )
    )
    docs_skipped = docs_skipped_result.scalar() or 0

    # Stalled: still "running" or "pending" with no progress for > 15 minutes
    stalled = False
    if job.status in ("running", "pending") and job.started_at:
        elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
        stalled = elapsed > 900  # 15 minutes

    return CrawlJobStatusResponse(
        job_id=str(job.id),
        kb_id=str(job.kb_id),
        status=job.status,
        pages_discovered=job.pages_discovered,
        pages_queued=job.pages_queued,
        pages_failed=job.pages_failed,
        docs_indexed=docs_indexed,
        docs_total=docs_total,
        docs_failed=docs_failed,
        docs_skipped=docs_skipped,
        stalled=stalled,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        phase=job.phase,
        error_message=job.error_message,
    )
