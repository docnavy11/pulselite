import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user, get_workspace, get_workspace_admin
from app.models.contacts import Contact
from app.models.conversations import Conversation
from app.models.intelligence import (
    ConversationAnalysis,
    GapEvent,
    RetrievalLog,
)
from app.models.knowledge import Chatbot
from app.models.organizational import Agent, Workspace
from app.schemas.intelligence import (
    ConversationAnalysisResponse,
    GapEventResponse,
    RetrievalLogResponse,
)
from app.services import conversation_service
from app.services.realtime import emit_task_event
from app.workers.tasks.analyze_conversation import analyze_conversation
from app.workers.tasks.compute_sentiment_trends import compute_sentiment_trends
from app.workers.tasks.cluster_gaps import cluster_gaps

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["intelligence"])


@router.get("/retrieval-logs", response_model=list[RetrievalLogResponse])
async def get_retrieval_logs(
    workspace_id: uuid.UUID = Depends(get_workspace),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100_000_000),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RetrievalLog)
        .where(RetrievalLog.workspace_id == workspace_id)
        .order_by(RetrievalLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.get("/gap-events", response_model=list[GapEventResponse])
async def get_gap_events(
    workspace_id: uuid.UUID = Depends(get_workspace),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100_000_000),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GapEvent)
        .where(GapEvent.workspace_id == workspace_id)
        .order_by(GapEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.get("/conversations/{conversation_id}/analysis", response_model=ConversationAnalysisResponse)
async def get_conversation_analysis(
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ConversationAnalysis).where(
            ConversationAnalysis.conversation_id == conversation_id,
            ConversationAnalysis.workspace_id == workspace_id,
        )
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return analysis


@router.post("/conversations/{conversation_id}/end")
async def end_conversation(
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    await conversation_service.update_conversation_status(db, conversation_id, "resolved")

    analyze_conversation.delay(str(conversation_id), str(workspace_id), force=True)  # type: ignore[attr-defined]

    return {"status": "resolved", "conversation_id": str(conversation_id)}


@router.get("/sentiment-by-segment")
async def get_sentiment_by_segment(
    workspace_id: uuid.UUID = Depends(get_workspace),
    days: int = Query(30, ge=1, le=90),
    segment: str = Query("chatbot"),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    if segment == "chatbot":
        result = await db.execute(
            select(
                Chatbot.name,
                func.avg(ConversationAnalysis.sentiment_score).label("avg_sentiment"),
                func.count().label("count"),
            )
            .join(Conversation, Conversation.id == ConversationAnalysis.conversation_id)
            .join(Chatbot, Chatbot.id == Conversation.chatbot_id)
            .where(
                ConversationAnalysis.workspace_id == workspace_id,
                ConversationAnalysis.sentiment_score.isnot(None),
                ConversationAnalysis.created_at >= cutoff,
            )
            .group_by(Chatbot.id, Chatbot.name)
            .order_by(func.count().desc())
        )
        rows = result.all()
        data = [
            {
                "name": row.name,
                "avg_sentiment": round(float(row.avg_sentiment), 3),
                "count": row.count,
            }
            for row in rows
        ]
    else:
        # segment == "contact"
        result = await db.execute(
            select(
                func.coalesce(Contact.name, Contact.email, "Anonymous").label("name"),
                func.avg(ConversationAnalysis.sentiment_score).label("avg_sentiment"),
                func.count().label("count"),
            )
            .join(Conversation, Conversation.id == ConversationAnalysis.conversation_id)
            .join(Contact, Contact.id == Conversation.contact_id)
            .where(
                ConversationAnalysis.workspace_id == workspace_id,
                ConversationAnalysis.sentiment_score.isnot(None),
                ConversationAnalysis.created_at >= cutoff,
            )
            .group_by(Contact.id, Contact.name, Contact.email)
            .order_by(func.count().desc())
            .limit(10)
        )
        rows = result.all()
        data = [
            {
                "name": row.name,
                "avg_sentiment": round(float(row.avg_sentiment), 3),
                "count": row.count,
            }
            for row in rows
        ]

    return {"data": data}


@router.post("/intelligence/trigger/analyze-all")
async def trigger_analyze_all_conversations(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger analysis for all unanalyzed conversations in this workspace."""
    # Find conversations that don't have an analysis yet
    analyzed_subq = select(ConversationAnalysis.conversation_id).where(
        ConversationAnalysis.workspace_id == workspace_id
    )
    result = await db.execute(
        select(Conversation.id).where(
            Conversation.workspace_id == workspace_id,
            Conversation.id.notin_(analyzed_subq),
        )
    )
    conversation_ids = [row[0] for row in result.all()]

    if not conversation_ids:
        return {"status": "ok", "conversations_queued": 0, "message": "All conversations are already analyzed"}

    task_id = str(uuid.uuid4())
    await emit_task_event(
        workspace_id, "started", "analyze_all", task_id,
        detail=f"Queued {len(conversation_ids)} conversations",
    )

    for cid in conversation_ids:
        analyze_conversation.delay(str(cid), str(workspace_id))  # type: ignore[attr-defined]

    await emit_task_event(
        workspace_id, "completed", "analyze_all", task_id,
        detail=f"Dispatched {len(conversation_ids)} analysis tasks",
    )

    return {"status": "dispatched", "conversations_queued": len(conversation_ids)}


@router.post("/intelligence/trigger/sentiment-trends")
async def trigger_sentiment_trends(
    workspace_id: uuid.UUID = Depends(get_workspace),
):
    """Manually trigger sentiment trends computation."""
    compute_sentiment_trends.delay()  # type: ignore[attr-defined]
    return {"status": "dispatched"}


@router.post("/intelligence/trigger/cluster-gaps")
async def trigger_cluster_gaps(
    workspace_id: uuid.UUID = Depends(get_workspace),
):
    """Manually trigger gap event clustering."""
    cluster_gaps.delay()  # type: ignore[attr-defined]
    return {"status": "dispatched"}


# ── Intelligence Config (admin-only) ─────────────────────────────────────────


class IntelligenceConfigUpdate(BaseModel):
    auto_analyze: bool | None = None
    sentiment_trends: bool | None = None
    gap_clustering: bool | None = None
    report_frequency: Literal["off", "daily", "weekly", "monthly"] | None = None
    report_recipients: list[str] | None = None
    report_sections: dict[str, bool] | None = None


DEFAULT_REPORT_SECTIONS = {
    "conversations": True,
    "confidence": True,
    "sentiment": True,
    "gaps": True,
    "top_topics": True,
    "qa_performance": True,
}


@router.get("/intelligence/config")
async def get_intelligence_config(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Get intelligence pipeline configuration for this workspace."""
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = result.scalar_one()
    config = ws.intelligence_config or {}
    return {
        "auto_analyze": config.get("auto_analyze", True),
        "sentiment_trends": config.get("sentiment_trends", True),
        "gap_clustering": config.get("gap_clustering", True),
        "report_frequency": config.get("report_frequency", "off"),
        "report_recipients": config.get("report_recipients", []),
        "report_sections": {**DEFAULT_REPORT_SECTIONS, **config.get("report_sections", {})},
    }


@router.put("/intelligence/config")
async def update_intelligence_config(
    body: IntelligenceConfigUpdate,
    workspace_id: uuid.UUID = Depends(get_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update intelligence pipeline configuration (admin only)."""
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = result.scalar_one()
    config = dict(ws.intelligence_config or {})
    if body.auto_analyze is not None:
        config["auto_analyze"] = body.auto_analyze
    if body.sentiment_trends is not None:
        config["sentiment_trends"] = body.sentiment_trends
    if body.gap_clustering is not None:
        config["gap_clustering"] = body.gap_clustering
    if body.report_frequency is not None:
        config["report_frequency"] = body.report_frequency
    if body.report_recipients is not None:
        config["report_recipients"] = body.report_recipients
    if body.report_sections is not None:
        config["report_sections"] = body.report_sections
    ws.intelligence_config = config
    await db.commit()
    return {
        "auto_analyze": config.get("auto_analyze", True),
        "sentiment_trends": config.get("sentiment_trends", True),
        "gap_clustering": config.get("gap_clustering", True),
        "report_frequency": config.get("report_frequency", "off"),
        "report_recipients": config.get("report_recipients", []),
        "report_sections": {**DEFAULT_REPORT_SECTIONS, **config.get("report_sections", {})},
    }
