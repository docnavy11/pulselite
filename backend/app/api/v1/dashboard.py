import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.conversations import Conversation, Message, MessageFeedback
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
    chatbot_id: uuid.UUID | None = Query(None),
    days: int = Query(30, ge=1, le=90),
):
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days)
    prev_period_start = period_start - timedelta(days=days)

    conv_base = [Conversation.workspace_id == workspace_id]
    if chatbot_id:
        conv_base.append(Conversation.chatbot_id == chatbot_id)

    current_result = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(Conversation.autonomous_resolved == True).label("resolved"),  # noqa: E712
            func.count().filter(Conversation.escalation_reason.isnot(None)).label("escalated"),
        )
        .select_from(Conversation)
        .where(*conv_base, Conversation.created_at >= period_start)
    )
    current = current_result.one()

    prev_result = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(Conversation.autonomous_resolved == True).label("resolved"),  # noqa: E712
        )
        .select_from(Conversation)
        .where(
            *conv_base,
            Conversation.created_at >= prev_period_start,
            Conversation.created_at < period_start,
        )
    )
    prev = prev_result.one()

    resolution_rate = current.resolved / current.total if current.total > 0 else 0.0
    prev_rate = prev.resolved / prev.total if prev.total > 0 else 0.0
    rate_trend = resolution_rate - prev_rate

    escalation_result = await db.execute(
        select(Conversation.escalation_reason, func.count())
        .where(
            *conv_base,
            Conversation.created_at >= period_start,
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
        .where(*conv_base, Conversation.created_at >= twelve_weeks_ago)
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
        .where(Article.workspace_id == workspace_id, Article.created_at >= period_start, Article.state == "published")
    )
    new_articles = articles_result.scalar() or 0

    gap_filters = [GapCluster.workspace_id == workspace_id, GapCluster.status == "open"]
    if chatbot_id:
        gap_filters.append(GapCluster.chatbot_id == chatbot_id)
    open_gaps_result = await db.execute(
        select(func.count()).select_from(GapCluster).where(*gap_filters)
    )
    open_gaps = open_gaps_result.scalar() or 0

    feedback_stmt = (
        select(MessageFeedback.rating, func.count().label("n"))
        .where(
            MessageFeedback.workspace_id == workspace_id,
            MessageFeedback.created_at >= period_start,
        )
        .group_by(MessageFeedback.rating)
    )
    if chatbot_id:
        feedback_stmt = (
            select(MessageFeedback.rating, func.count().label("n"))
            .join(Message, MessageFeedback.message_id == Message.id)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                MessageFeedback.workspace_id == workspace_id,
                MessageFeedback.created_at >= period_start,
                Conversation.chatbot_id == chatbot_id,
            )
            .group_by(MessageFeedback.rating)
        )
    feedback_result = await db.execute(feedback_stmt)
    feedback_counts: dict[str, int] = {row.rating: row.n for row in feedback_result.all()}

    # Top topics: count both total and resolved per topic
    top_topics_params: dict = {"ws": str(workspace_id), "cutoff": period_start, "chatbot_id": str(chatbot_id) if chatbot_id else None}
    top_topics_result = await db.execute(
        text(
            "SELECT topic,"
            "       count(*) AS total_count,"
            "       count(*) FILTER (WHERE c.autonomous_resolved = TRUE) AS resolved_count"
            " FROM conversation_analysis ca"
            " JOIN conversations c ON c.id = ca.conversation_id"
            " CROSS JOIN LATERAL unnest(ca.topics) AS topic"
            " WHERE ca.workspace_id = :ws"
            "   AND ca.created_at >= :cutoff"
            "   AND (CAST(:chatbot_id AS uuid) IS NULL OR c.chatbot_id = CAST(:chatbot_id AS uuid))"
            " GROUP BY topic"
            " ORDER BY total_count DESC"
            " LIMIT 5"
        ),
        top_topics_params,
    )
    top_topics_rows = top_topics_result.all()

    # For each topic, find a relevant example query by matching the topic keyword
    # against retrieval log queries from those conversations
    top_topics = []
    for row in top_topics_rows:
        topic_name = row[0]
        total_count = row[1]
        resolved_count = row[2]

        # Find a relevant example query, preferring ones that match the topic keyword
        example_result = await db.execute(
            text(
                "SELECT rl.query"
                " FROM retrieval_logs rl"
                " JOIN conversations c ON c.id = rl.conversation_id"
                " JOIN conversation_analysis ca ON ca.conversation_id = c.id"
                " WHERE ca.workspace_id = :ws"
                "   AND ca.created_at >= :cutoff"
                "   AND :topic = ANY(ca.topics)"
                "   AND length(rl.query) > 10"
                "   AND (CAST(:chatbot_id AS uuid) IS NULL OR c.chatbot_id = CAST(:chatbot_id AS uuid))"
                " ORDER BY"
                "   (rl.query ILIKE '%' || :topic || '%')::int DESC,"
                "   rl.escalated::int ASC,"
                "   length(rl.query) DESC"
                " LIMIT 1"
            ),
            {**top_topics_params, "topic": topic_name},
        )
        example_query = example_result.scalar_one_or_none()

        # Filter out trivial queries that aren't useful as examples
        if example_query and len(example_query.strip()) < 15:
            example_query = None

        top_topics.append({
            "topic": topic_name,
            "total_count": total_count,
            "resolved_count": resolved_count,
            "resolution_rate": round(resolved_count / total_count, 4) if total_count > 0 else 0.0,
            "example_query": example_query,
        })

    # Recent negative feedback with comments
    neg_feedback_stmt = (
        select(
            MessageFeedback.id,
            MessageFeedback.comment,
            MessageFeedback.created_at,
            Message.content.label("message_content"),
        )
        .join(Message, MessageFeedback.message_id == Message.id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            MessageFeedback.workspace_id == workspace_id,
            MessageFeedback.rating == "thumbs_down",
            MessageFeedback.comment.isnot(None),
            MessageFeedback.comment != "",
            MessageFeedback.created_at >= period_start,
        )
        .order_by(MessageFeedback.created_at.desc())
        .limit(3)
    )
    if chatbot_id:
        neg_feedback_stmt = neg_feedback_stmt.where(Conversation.chatbot_id == chatbot_id)
    neg_feedback_result = await db.execute(neg_feedback_stmt)
    recent_negative_feedback = [
        {
            "id": str(row.id),
            "comment": row.comment,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "message_content": row.message_content,
        }
        for row in neg_feedback_result.all()
    ]

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
        "recent_negative_feedback": recent_negative_feedback,
    }


@router.get("/sentiment-trends")
async def get_sentiment_trends(
    workspace_id: uuid.UUID = Depends(get_workspace),
    days: int = Query(30, ge=1, le=90),
    chatbot_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    day_col = func.date(ConversationAnalysis.created_at).label("day")
    filters = [
        ConversationAnalysis.workspace_id == workspace_id,
        ConversationAnalysis.sentiment_score.isnot(None),
        ConversationAnalysis.created_at >= cutoff,
    ]

    stmt = select(
        day_col,
        func.avg(ConversationAnalysis.sentiment_score).label("avg_sentiment"),
        func.count(ConversationAnalysis.id).label("count"),
    )

    if chatbot_id:
        stmt = stmt.join(
            Conversation,
            ConversationAnalysis.conversation_id == Conversation.id,
        )
        filters.append(Conversation.chatbot_id == chatbot_id)

    stmt = stmt.where(*filters).group_by(day_col).order_by(day_col.desc())

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
