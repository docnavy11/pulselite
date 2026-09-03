"""Workspace-wide logs endpoints: crawl runs and document ingestion."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace, get_workspace_admin
from app.models.contacts import Contact
from app.models.conversations import Conversation
from app.models.intelligence import ConversationAnalysis, RetrievalLog
from app.models.knowledge import Chatbot, CrawlJob, Document, KnowledgeBase
from app.models.task_log import BackgroundTaskLog
from app.schemas.logs import (
    AnalysisRunLogItem,
    AnalysisRunLogResponse,
    CrawlRunLogItem,
    CrawlRunLogResponse,
    DocumentLogItem,
    DocumentLogResponse,
    RetrievalLogItem,
    RetrievalLogResponse,
)
from app.schemas.worker_health import (
    PerformanceStats,
    QueueStats,
    ReliabilityStats,
    TaskPerformance,
    TimeseriesBucket,
    TopError,
    WorkerHealthResponse,
)

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["logs"])


@router.get("/logs/crawl-runs", response_model=CrawlRunLogResponse)
async def list_crawl_run_logs(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
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
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
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


@router.get("/logs/analysis-runs", response_model=AnalysisRunLogResponse)
async def list_analysis_run_logs(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> AnalysisRunLogResponse:
    """List conversation analysis runs, newest first."""
    total_result = await db.execute(
        select(func.count(ConversationAnalysis.id)).where(
            ConversationAnalysis.workspace_id == workspace_id
        )
    )
    total = total_result.scalar_one()

    if total == 0:
        return AnalysisRunLogResponse(items=[], total=0)

    rows = (
        await db.execute(
            select(ConversationAnalysis, Conversation, Chatbot, Contact)
            .join(Conversation, Conversation.id == ConversationAnalysis.conversation_id)
            .outerjoin(Chatbot, Chatbot.id == Conversation.chatbot_id)
            .outerjoin(Contact, Contact.id == Conversation.contact_id)
            .where(ConversationAnalysis.workspace_id == workspace_id)
            .order_by(ConversationAnalysis.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    items = []
    for row in rows:
        analysis: ConversationAnalysis = row.ConversationAnalysis
        conv: Conversation = row.Conversation
        chatbot: Chatbot | None = row.Chatbot
        contact: Contact | None = row.Contact
        items.append(
            AnalysisRunLogItem(
                id=str(analysis.id),
                conversation_id=str(analysis.conversation_id),
                chatbot_id=str(chatbot.id) if chatbot else None,
                chatbot_name=chatbot.name if chatbot else None,
                contact_name=contact.name if contact else (contact.email if contact else None),
                sentiment_score=analysis.sentiment_score,
                sentiment_label=analysis.sentiment_label,
                intent_primary=analysis.intent_primary,
                outcome_category=analysis.outcome_category,
                topics=analysis.topics,
                summary=analysis.summary,
                llm_model=analysis.llm_model,
                processing_ms=analysis.processing_ms,
                created_at=analysis.created_at.isoformat(),
            )
        )
    return AnalysisRunLogResponse(items=items, total=total)


@router.get("/logs/retrievals", response_model=RetrievalLogResponse)
async def list_retrieval_logs(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
    chatbot_id: uuid.UUID | None = Query(default=None),
) -> RetrievalLogResponse:
    """List retrieval logs, newest first. Optionally filter by chatbot."""
    count_query = select(func.count(RetrievalLog.id)).where(RetrievalLog.workspace_id == workspace_id)
    if chatbot_id:
        count_query = count_query.where(RetrievalLog.chatbot_id == chatbot_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    if total == 0:
        return RetrievalLogResponse(items=[], total=0)

    data_query = (
        select(RetrievalLog)
        .where(RetrievalLog.workspace_id == workspace_id)
        .order_by(RetrievalLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if chatbot_id:
        data_query = data_query.where(RetrievalLog.chatbot_id == chatbot_id)

    rows_result = await db.execute(data_query)
    rows = rows_result.scalars().all()

    items = []
    for log in rows:
        items.append(
            RetrievalLogItem(
                id=str(log.id),
                chatbot_id=str(log.chatbot_id),
                conversation_id=str(log.conversation_id) if log.conversation_id else None,
                message_id=str(log.message_id) if log.message_id else None,
                query=log.query,
                confidence_score=log.confidence_score,
                confidence_avg=log.confidence_avg,
                chunk_count=len(log.retrieved_chunk_ids) if log.retrieved_chunk_ids else None,
                reranked=log.reranked,
                escalated=log.escalated,
                response_generated=log.response_generated,
                retrieval_ms=log.retrieval_ms,
                generation_ms=log.generation_ms,
                created_at=log.created_at.isoformat(),
            )
        )
    return RetrievalLogResponse(items=items, total=total)


@router.get("/workers/health", response_model=WorkerHealthResponse)
async def get_worker_health(
    workspace_id: uuid.UUID = Depends(get_workspace_admin),
    db: AsyncSession = Depends(get_db),
    window: Literal["1h", "24h", "7d"] = "24h",
) -> WorkerHealthResponse:
    """Aggregated worker health metrics for the workspace."""
    from sqlalchemy import desc

    window_map = {"1h": timedelta(hours=1), "24h": timedelta(hours=24), "7d": timedelta(days=7)}
    cutoff = datetime.now(timezone.utc) - window_map[window]

    # Queue stats (live — no time window filter)
    queue_result = await db.execute(
        select(
            BackgroundTaskLog.status,
            func.count(BackgroundTaskLog.id),
        )
        .where(
            BackgroundTaskLog.workspace_id == workspace_id,
            BackgroundTaskLog.status.in_(["pending", "running"]),
        )
        .group_by(BackgroundTaskLog.status)
    )
    queue_counts = dict(queue_result.all())
    pending = queue_counts.get("pending", 0)
    running = queue_counts.get("running", 0)

    # All tasks in window
    window_filter = [
        BackgroundTaskLog.workspace_id == workspace_id,
        BackgroundTaskLog.started_at >= cutoff,
    ]

    # Reliability — only count completed + failed tasks (exclude running/pending)
    rel_result = await db.execute(
        select(
            func.count(BackgroundTaskLog.id),
            func.count(BackgroundTaskLog.id).filter(BackgroundTaskLog.status == "completed"),
            func.count(BackgroundTaskLog.id).filter(BackgroundTaskLog.status == "failed"),
            func.coalesce(func.sum(BackgroundTaskLog.retry_count), 0),
        ).where(
            *window_filter,
            BackgroundTaskLog.status.in_(["completed", "failed"]),
        )
    )
    total, succeeded, failed, total_retries = rel_result.one()
    failure_rate = round((failed / total * 100) if total > 0 else 0.0, 2)

    # Throughput
    hours = window_map[window].total_seconds() / 3600
    throughput = round(succeeded / hours, 1) if hours > 0 else 0.0

    # Top errors
    errors_result = await db.execute(
        select(
            BackgroundTaskLog.task_name,
            BackgroundTaskLog.error,
            func.count(BackgroundTaskLog.id).label("cnt"),
        )
        .where(
            *window_filter,
            BackgroundTaskLog.status == "failed",
            BackgroundTaskLog.error.isnot(None),
        )
        .group_by(BackgroundTaskLog.task_name, BackgroundTaskLog.error)
        .order_by(desc("cnt"))
        .limit(10)
    )
    top_errors = [TopError(task_name=r[0], error=r[1], count=r[2]) for r in errors_result.all()]

    # Performance by task
    perf_result = await db.execute(
        select(
            BackgroundTaskLog.task_name,
            func.count(BackgroundTaskLog.id).label("count"),
            (
                func.count(BackgroundTaskLog.id).filter(BackgroundTaskLog.status == "completed")
                * 100.0
                / func.nullif(func.count(BackgroundTaskLog.id), 0)
            ).label("success_rate"),
            func.avg(BackgroundTaskLog.duration_ms).filter(
                BackgroundTaskLog.duration_ms.isnot(None)
            ).label("avg_ms"),
            func.percentile_cont(0.95).within_group(
                BackgroundTaskLog.duration_ms
            ).label("p95_ms"),
        )
        .where(
            *window_filter,
            BackgroundTaskLog.duration_ms.isnot(None),
        )
        .group_by(BackgroundTaskLog.task_name)
        .order_by(desc("count"))
    )
    by_task_rows = perf_result.all()

    # Also get last_failure_at per task (separate query to avoid filter on within_group issues)
    last_fail_result = await db.execute(
        select(
            BackgroundTaskLog.task_name,
            func.max(BackgroundTaskLog.started_at).label("last_fail"),
        )
        .where(
            *window_filter,
            BackgroundTaskLog.status == "failed",
        )
        .group_by(BackgroundTaskLog.task_name)
    )
    last_fail_by_task = {r.task_name: r.last_fail for r in last_fail_result.all()}

    # Also get total count per task (including tasks with null duration_ms)
    total_count_result = await db.execute(
        select(
            BackgroundTaskLog.task_name,
            func.count(BackgroundTaskLog.id).label("total_count"),
            (
                func.count(BackgroundTaskLog.id).filter(BackgroundTaskLog.status == "completed")
                * 100.0
                / func.nullif(func.count(BackgroundTaskLog.id), 0)
            ).label("success_rate"),
        )
        .where(*window_filter)
        .group_by(BackgroundTaskLog.task_name)
        .order_by(desc("total_count"))
    )
    total_counts = {r.task_name: (r.total_count, r.success_rate) for r in total_count_result.all()}

    # Merge perf data with total counts
    perf_by_task = {r.task_name: r for r in by_task_rows}
    all_task_names_ordered = sorted(total_counts.keys(), key=lambda n: total_counts[n][0], reverse=True)

    by_task = []
    for task_name in all_task_names_ordered:
        total_count, success_rate = total_counts[task_name]
        perf = perf_by_task.get(task_name)
        by_task.append(
            TaskPerformance(
                task_name=task_name,
                count=total_count,
                success_rate_pct=round(float(success_rate or 0), 1),
                avg_duration_ms=round(float(perf.avg_ms)) if perf and perf.avg_ms else None,
                p95_duration_ms=round(float(perf.p95_ms)) if perf and perf.p95_ms else None,
                last_failure_at=last_fail_by_task.get(task_name),
            )
        )

    # Timeseries
    if window == "7d":
        bucket_expr = func.date_trunc("day", BackgroundTaskLog.started_at)
    else:
        bucket_expr = func.date_trunc("hour", BackgroundTaskLog.started_at)

    ts_result = await db.execute(
        select(
            bucket_expr.label("bucket"),
            func.count(BackgroundTaskLog.id).filter(
                BackgroundTaskLog.status == "completed"
            ).label("completed"),
            func.count(BackgroundTaskLog.id).filter(
                BackgroundTaskLog.status == "failed"
            ).label("failed"),
        )
        .where(*window_filter)
        .group_by("bucket")
        .order_by("bucket")
    )
    timeseries = [
        TimeseriesBucket(bucket=r.bucket, completed=r.completed, failed=r.failed)
        for r in ts_result.all()
    ]

    return WorkerHealthResponse(
        queue=QueueStats(pending=pending, running=running, throughput_per_hour=throughput),
        reliability=ReliabilityStats(
            total=total,
            succeeded=succeeded,
            failed=failed,
            failure_rate_pct=failure_rate,
            total_retries=total_retries,
            top_errors=top_errors,
        ),
        performance=PerformanceStats(by_task=by_task),
        timeseries=timeseries,
    )


@router.get("/server-logs")
async def get_server_logs(
    workspace_id: uuid.UUID = Depends(get_workspace_admin),
    limit: int = Query(default=100, le=1000),
    level: str | None = Query(default=None, description="Filter by log level: DEBUG, INFO, WARNING, ERROR"),
    logger_name: str | None = Query(default=None, description="Filter by logger name"),
):
    """Get recent server log entries from the in-memory buffer. Admin only."""
    from app.services.log_buffer import LogBuffer

    buffer = LogBuffer.get_instance()
    entries = buffer.get_entries(limit=limit, level=level, logger_name=logger_name)
    return {"entries": entries, "total": len(entries)}
