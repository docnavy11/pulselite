import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.contacts import Contact
from app.models.conversations import Conversation
from app.models.intelligence import (
    AutonomousResolutionStats,
    ConversationAnalysis,
    GapCluster,
    LeadScore,
    TopicCluster,
)
from app.models.knowledge import Article
from app.models.organizational import Agent

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["dashboard"])


@router.get("/dashboard")
async def get_dashboard(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    prev_week_start = now - timedelta(days=14)

    current_result = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(Conversation.autonomous_resolved == True).label("resolved"),  # noqa: E712
            func.count().filter(Conversation.escalation_reason.isnot(None)).label("escalated"),
        )
        .select_from(Conversation)
        .where(Conversation.workspace_id == workspace_id, Conversation.created_at >= week_start)
    )
    current = current_result.one()

    prev_result = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(Conversation.autonomous_resolved == True).label("resolved"),  # noqa: E712
        )
        .select_from(Conversation)
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= prev_week_start,
            Conversation.created_at < week_start,
        )
    )
    prev = prev_result.one()

    resolution_rate = current.resolved / current.total if current.total > 0 else 0.0
    prev_rate = prev.resolved / prev.total if prev.total > 0 else 0.0
    rate_trend = resolution_rate - prev_rate

    escalation_result = await db.execute(
        select(Conversation.escalation_reason, func.count())
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= week_start,
            Conversation.escalation_reason.isnot(None),
        )
        .group_by(Conversation.escalation_reason)
    )
    escalation_breakdown = {row[0]: row[1] for row in escalation_result.all()}

    trend_data = []
    for i in range(12):
        w_end = now - timedelta(weeks=i)
        w_start = w_end - timedelta(weeks=1)
        week_result = await db.execute(
            select(
                func.count().label("total"),
                func.count().filter(Conversation.autonomous_resolved == True).label("resolved"),  # noqa: E712
            )
            .select_from(Conversation)
            .where(
                Conversation.workspace_id == workspace_id,
                Conversation.created_at >= w_start,
                Conversation.created_at < w_end,
            )
        )
        week_row = week_result.one()
        trend_data.append(
            {
                "week_start": w_start.date().isoformat(),
                "total": week_row.total,
                "resolved": week_row.resolved,
                "rate": week_row.resolved / week_row.total if week_row.total > 0 else 0.0,
            }
        )
    trend_data.reverse()

    articles_result = await db.execute(
        select(func.count())
        .select_from(Article)
        .where(Article.workspace_id == workspace_id, Article.created_at >= week_start, Article.state == "published")
    )
    new_articles = articles_result.scalar() or 0

    open_gaps_result = await db.execute(
        select(func.count())
        .select_from(GapCluster)
        .where(GapCluster.workspace_id == workspace_id, GapCluster.status == "open")
    )
    open_gaps = open_gaps_result.scalar() or 0

    hot_leads_result = await db.execute(
        select(func.count())
        .select_from(LeadScore)
        .where(LeadScore.workspace_id == workspace_id, LeadScore.tier == "hot")
    )
    hot_leads = hot_leads_result.scalar() or 0

    anomalies_result = await db.execute(
        select(func.count())
        .select_from(TopicCluster)
        .where(TopicCluster.workspace_id == workspace_id, TopicCluster.anomaly_detected == True)  # noqa: E712
    )
    topic_anomalies = anomalies_result.scalar() or 0

    velocity_result = await db.execute(
        select(AutonomousResolutionStats.knowledge_velocity)
        .where(AutonomousResolutionStats.workspace_id == workspace_id)
        .order_by(AutonomousResolutionStats.period_date.desc())
        .limit(1)
    )
    knowledge_velocity = velocity_result.scalar() or 0.0

    return {
        "resolution_rate": round(resolution_rate, 4),
        "resolution_rate_trend": round(rate_trend, 4),
        "knowledge_velocity": round(float(knowledge_velocity), 4),
        "escalation_breakdown": escalation_breakdown,
        "resolution_trend": trend_data,
        "stats": {
            "total_conversations": current.total,
            "resolved": current.resolved,
            "escalated": current.escalated,
            "new_articles": new_articles,
        },
        "intelligence": {
            "open_gaps": open_gaps,
            "hot_leads": hot_leads,
            "topic_anomalies": topic_anomalies,
        },
    }


@router.get("/topics")
async def list_topics(
    workspace_id: uuid.UUID = Depends(get_workspace),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100_000_000),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(
        select(TopicCluster)
        .where(TopicCluster.workspace_id == workspace_id)
        .order_by(TopicCluster.conversation_count.desc())
        .limit(limit)
        .offset(offset)
    )
    topics = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "label": t.label,
            "keywords": t.keywords,
            "conversation_count": t.conversation_count,
            "volume_trend": t.volume_trend,
            "anomaly_detected": t.anomaly_detected,
            "anomaly_type": t.anomaly_type,
            "date_range_start": t.date_range_start.isoformat() if t.date_range_start else None,
            "date_range_end": t.date_range_end.isoformat() if t.date_range_end else None,
        }
        for t in topics
    ]


@router.get("/topics/{topic_id}")
async def get_topic_detail(
    topic_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    from fastapi import HTTPException, status

    result = await db.execute(
        select(TopicCluster).where(
            TopicCluster.id == topic_id,
            TopicCluster.workspace_id == workspace_id,
        )
    )
    topic = result.scalar_one_or_none()
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    conv_result = await db.execute(
        select(
            ConversationAnalysis.conversation_id,
            ConversationAnalysis.summary,
            ConversationAnalysis.sentiment_label,
        )
        .where(
            ConversationAnalysis.workspace_id == workspace_id,
            ConversationAnalysis.topics.any(topic.label),
        )
        .limit(20)
    )
    conversations = [
        {
            "conversation_id": str(row[0]),
            "summary": row[1],
            "sentiment": row[2],
        }
        for row in conv_result.all()
    ]

    return {
        "id": str(topic.id),
        "label": topic.label,
        "keywords": topic.keywords,
        "conversation_count": topic.conversation_count,
        "volume_trend": topic.volume_trend,
        "anomaly_detected": topic.anomaly_detected,
        "anomaly_type": topic.anomaly_type,
        "conversations": conversations,
    }


@router.get("/sentiment-trends")
async def get_sentiment_trends(
    workspace_id: uuid.UUID = Depends(get_workspace),
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    day_col = func.date(ConversationAnalysis.created_at).label("day")
    stmt = (
        select(
            day_col,
            func.avg(ConversationAnalysis.sentiment_score).label("avg_sentiment"),
            func.count(ConversationAnalysis.id).label("count"),
        )
        .where(
            ConversationAnalysis.workspace_id == workspace_id,
            ConversationAnalysis.sentiment_score.isnot(None),
            ConversationAnalysis.created_at >= cutoff,
        )
        .group_by(day_col)
        .order_by(day_col.desc())
    )
    rows = (await db.execute(stmt)).all()
    data = [
        {
            "date": str(row[0]),
            "avg_sentiment": round(float(row[1]), 3) if row[1] else None,
            "count": row[2],
        }
        for row in rows
    ]
    return {"data": data}


@router.get("/feature-requests")
async def list_feature_requests(
    workspace_id: uuid.UUID = Depends(get_workspace),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(
        select(TopicCluster)
        .where(
            TopicCluster.workspace_id == workspace_id,
            TopicCluster.label.startswith("FR: "),
        )
        .order_by(TopicCluster.conversation_count.desc())
        .limit(limit)
    )
    clusters = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "label": c.label.removeprefix("FR: "),
            "keywords": c.keywords,
            "count": c.conversation_count,
            "volume_trend": c.volume_trend,
        }
        for c in clusters
    ]


@router.get("/leads")
async def list_leads(
    workspace_id: uuid.UUID = Depends(get_workspace),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100_000_000),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(
        select(LeadScore, Contact)
        .join(Contact, LeadScore.contact_id == Contact.id)
        .where(LeadScore.workspace_id == workspace_id)
        .order_by(LeadScore.score.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()
    return [
        {
            "id": str(ls.id),
            "contact_id": str(ls.contact_id),
            "contact_name": c.name,
            "contact_email": c.email,
            "score": ls.score,
            "tier": ls.tier,
            "signals": ls.signals,
            "scored_at": ls.scored_at.isoformat(),
        }
        for ls, c in rows
    ]
