"""Workspace-wide logs endpoints: crawl runs and document ingestion."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace
from app.models.knowledge import Chatbot, CrawlJob, Document, KnowledgeBase
from app.schemas.logs import (
    CrawlRunLogItem,
    CrawlRunLogResponse,
    DocumentLogItem,
    DocumentLogResponse,
)

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["logs"])


@router.get("/logs/crawl-runs", response_model=CrawlRunLogResponse)
async def list_crawl_run_logs(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CrawlRunLogResponse:
    # Total count
    total_result = await db.execute(
        select(func.count(CrawlJob.id)).where(CrawlJob.workspace_id == workspace_id)
    )
    total = total_result.scalar_one()

    if total == 0:
        return CrawlRunLogResponse(items=[], total=0)

    # Fetch paginated jobs with KB + Chatbot join
    jobs_result = await db.execute(
        select(CrawlJob, KnowledgeBase, Chatbot)
        .outerjoin(KnowledgeBase, CrawlJob.kb_id == KnowledgeBase.id)
        .outerjoin(Chatbot, KnowledgeBase.chatbot_id == Chatbot.id)
        .where(CrawlJob.workspace_id == workspace_id)
        .order_by(CrawlJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = jobs_result.all()

    if not rows:
        return CrawlRunLogResponse(items=[], total=total)

    # Batch-compute docs_indexed per KB
    kb_ids = [row.KnowledgeBase.id for row in rows if row.KnowledgeBase]
    indexed_by_kb: dict[uuid.UUID, int] = {}
    if kb_ids:
        counts_result = await db.execute(
            select(Document.knowledge_base_id, func.count(Document.id))
            .where(
                Document.knowledge_base_id.in_(kb_ids),
                Document.status == "indexed",
            )
            .group_by(Document.knowledge_base_id)
        )
        indexed_by_kb = dict(counts_result.all())

    items = []
    for row in rows:
        job: CrawlJob = row.CrawlJob
        kb: KnowledgeBase | None = row.KnowledgeBase
        chatbot: Chatbot | None = row.Chatbot
        items.append(
            CrawlRunLogItem(
                job_id=str(job.id),
                chatbot_id=str(chatbot.id) if chatbot else None,
                chatbot_name=chatbot.name if chatbot else None,
                root_url=job.root_url,
                status=job.status,
                phase=job.phase,
                pages_discovered=job.pages_discovered,
                pages_queued=job.pages_queued,
                pages_failed=job.pages_failed,
                docs_indexed=indexed_by_kb.get(kb.id, 0) if kb else 0,
                error_message=job.error_message,
                created_at=job.created_at.isoformat(),
                started_at=job.started_at.isoformat() if job.started_at else None,
                completed_at=job.completed_at.isoformat() if job.completed_at else None,
            )
        )
    return CrawlRunLogResponse(items=items, total=total)


@router.get("/logs/documents", response_model=DocumentLogResponse)
async def list_document_logs(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentLogResponse:
    # Total count
    total_result = await db.execute(
        select(func.count(Document.id)).where(Document.workspace_id == workspace_id)
    )
    total = total_result.scalar_one()

    if total == 0:
        return DocumentLogResponse(items=[], total=0)

    # Fetch paginated docs with KB + Chatbot join, newest first
    docs_result = await db.execute(
        select(Document, KnowledgeBase, Chatbot)
        .outerjoin(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
        .outerjoin(Chatbot, KnowledgeBase.chatbot_id == Chatbot.id)
        .where(Document.workspace_id == workspace_id)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = docs_result.all()

    items = []
    for row in rows:
        doc: Document = row.Document
        kb: KnowledgeBase | None = row.KnowledgeBase
        chatbot: Chatbot | None = row.Chatbot
        items.append(
            DocumentLogItem(
                id=str(doc.id),
                title=doc.title,
                source_url=doc.source_url,
                source_type=doc.source_type,
                status=doc.status,
                chunk_count=doc.chunk_count or 0,
                last_indexed_at=doc.last_indexed_at.isoformat() if doc.last_indexed_at else None,
                error_message=doc.error_message,
                ingestion_steps=doc.ingestion_steps,
                knowledge_base_id=str(kb.id) if kb else "",
                knowledge_base_name=kb.name if kb else "Unknown",
                chatbot_id=str(chatbot.id) if chatbot else None,
                chatbot_name=chatbot.name if chatbot else None,
            )
        )
    return DocumentLogResponse(items=items, total=total)
