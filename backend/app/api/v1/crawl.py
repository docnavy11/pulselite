# backend/app/api/v1/crawl.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_workspace
from app.models.knowledge import CrawlJob, Document
from app.schemas.crawl import CrawlJobStatusResponse, CrawlRequest, CrawlResponse
from app.services.crawl_service import start_crawl

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["crawl"])


@router.post("/crawl", response_model=CrawlResponse, status_code=201)
async def crawl_website_endpoint(
    body: CrawlRequest,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await start_crawl(db, workspace_id, body.url, body.max_pages, body.knowledge_base_id, body.chatbot_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return CrawlResponse(
        job_id=result.job_id,
        kb_id=result.kb_id,
        pages_discovered=result.pages_discovered,
        pages_queued=result.pages_queued,
        over_limit=result.over_limit,
        limit=result.limit,
    )


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

    # Count ingestion progress for this KB
    docs_total_result = await db.execute(
        select(func.count()).where(Document.knowledge_base_id == job.kb_id)
    )
    docs_indexed_result = await db.execute(
        select(func.count()).where(
            Document.knowledge_base_id == job.kb_id,
            Document.status == "indexed",
        )
    )
    docs_total = docs_total_result.scalar() or 0
    docs_indexed = docs_indexed_result.scalar() or 0

    return CrawlJobStatusResponse(
        job_id=str(job.id),
        kb_id=str(job.kb_id),
        status=job.status,
        pages_discovered=job.pages_discovered,
        pages_queued=job.pages_queued,
        pages_failed=job.pages_failed,
        docs_indexed=docs_indexed,
        docs_total=docs_total,
        over_limit=job.over_limit,
        limit=job.max_pages,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )
