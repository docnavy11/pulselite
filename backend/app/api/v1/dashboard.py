import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.conversations import Conversation, MessageFeedback
from app.models.intelligence import (
    ConversationAnalysis,
    GapCluster,
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

    twelve_weeks_ago = now - timedelta(weeks=12)
    week_trunc = func.date_trunc(text("'week'"), Conversation.created_at)
    trend_stmt = (
        select(
            week_trunc.label("week"),
            func.count(Conversation.id).label("total"),
            func.count(Conversation.id).filter(Conversation.autonomous_resolved == True).label("resolved"),  # noqa: E712
        )
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_at >= twelve_weeks_ago,
        )
        .group_by(week_trunc)
        .order_by(week_trunc)
    )
    trend_result = await db.execute(trend_stmt)
    week_rows = {row.week.replace(tzinfo=None): row for row in trend_result.all()}

    trend_data = []
    for i in range(11, -1, -1):
        w_end = now - timedelta(weeks=i)
        w_start = w_end - timedelta(weeks=1)
        # Align to Monday (date_trunc("week") starts on Monday in PostgreSQL)
        week_key = w_start.replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
        week_key -= timedelta(days=week_key.weekday())
        row = week_rows.get(week_key)
        total = row.total if row else 0
        resolved = row.resolved if row else 0
        trend_data.append(
            {
                "week_start": w_start.date().isoformat(),
                "total": total,
                "resolved": resolved,
                "rate": resolved / total if total > 0 else 0.0,
            }
        )

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

    thirty_days_ago = now - timedelta(days=30)
    feedback_result = await db.execute(
        select(MessageFeedback.rating, func.count().label("n"))
        .where(
            MessageFeedback.workspace_id == workspace_id,
            MessageFeedback.created_at >= thirty_days_ago,
        )
        .group_by(MessageFeedback.rating)
    )
    feedback_counts: dict[str, int] = {row.rating: row.n for row in feedback_result.all()}

    top_topics_result = await db.execute(
        text("""
            SELECT topic, count(*) AS n
            FROM conversation_analysis ca
            JOIN conversations c ON c.id = ca.conversation_id
            CROSS JOIN LATERAL unnest(ca.topics) AS topic
            WHERE ca.workspace_id = :ws
              AND c.autonomous_resolved = TRUE
              AND ca.created_at >= :cutoff
            GROUP BY topic
            ORDER BY n DESC
            LIMIT 5
        """),
        {"ws": str(workspace_id), "cutoff": thirty_days_ago},
    )
    top_topics = [{"topic": row[0], "count": row[1]} for row in top_topics_result.all()]

    return {
        "resolution_rate": round(resolution_rate, 4),
        "resolution_rate_trend": round(rate_trend, 4),
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
        },
        "feedback": {
            "thumbs_up": feedback_counts.get("thumbs_up", 0),
            "thumbs_down": feedback_counts.get("thumbs_down", 0),
        },
        "top_topics": top_topics,
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


