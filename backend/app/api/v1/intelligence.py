import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.contacts import Contact
from app.models.conversations import Conversation
from app.models.intelligence import (
    ConversationAnalysis,
    GapEvent,
    RetrievalLog,
)
from app.models.knowledge import Chatbot
from app.models.organizational import Agent
from app.schemas.intelligence import (
    ConversationAnalysisResponse,
    GapEventResponse,
    RetrievalLogResponse,
)
from app.services import conversation_service
from app.workers.tasks.analyze_conversation import analyze_conversation

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

    analyze_conversation.delay(str(conversation_id), str(workspace_id))  # type: ignore[attr-defined]

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


