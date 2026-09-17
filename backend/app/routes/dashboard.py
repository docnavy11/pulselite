"""Dashboard route — matches the React dashboard KPIs, topics, gaps."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.conversations import Conversation, MessageFeedback
from app.models.intelligence import ConversationAnalysis, GapCluster
from app.models.knowledge import Chatbot

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    if not workspace:
        from fastapi.responses import RedirectResponse

        return RedirectResponse("/login")
    ws_id = workspace.id
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Total conversations (all time)
    total_convs = (
        await db.execute(select(func.count(Conversation.id)).where(Conversation.workspace_id == ws_id))
    ).scalar_one()

    # Conversations 30d
    convs_30d = (
        await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.workspace_id == ws_id,
                Conversation.created_at >= thirty_days_ago,
            )
        )
    ).scalar_one()

    # Resolution rate
    resolved = (
        await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.workspace_id == ws_id,
                Conversation.autonomous_resolved == True,
            )
        )
    ).scalar_one()
    resolution_rate = round(resolved / total_convs * 100) if total_convs > 0 else 0

    # Escalated (30d)
    escalated = (
        await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.workspace_id == ws_id,
                Conversation.created_at >= thirty_days_ago,
                Conversation.outcome == "escalated_to_human",
            )
        )
    ).scalar_one()

    # Feedback
    thumbs_up = (
        await db.execute(
            select(func.count(MessageFeedback.id)).where(
                MessageFeedback.workspace_id == ws_id,
                MessageFeedback.rating == "thumbs_up",
            )
        )
    ).scalar_one()
    thumbs_down = (
        await db.execute(
            select(func.count(MessageFeedback.id)).where(
                MessageFeedback.workspace_id == ws_id,
                MessageFeedback.rating == "thumbs_down",
            )
        )
    ).scalar_one()
    satisfaction = round(thumbs_up / (thumbs_up + thumbs_down) * 100, 1) if (thumbs_up + thumbs_down) > 0 else 0

    # Average sentiment
    avg_sentiment = (
        await db.execute(
            select(func.avg(ConversationAnalysis.sentiment_score)).where(
                ConversationAnalysis.workspace_id == ws_id,
                ConversationAnalysis.sentiment_score.isnot(None),
            )
        )
    ).scalar_one()
    avg_sentiment = round(float(avg_sentiment), 2) if avg_sentiment else None

    # Top topics (from conversation analysis)
    top_topics = []
    topics_result = await db.execute(
        select(func.unnest(ConversationAnalysis.topics).label("topic")).where(
            ConversationAnalysis.workspace_id == ws_id
        )
    )
    topic_counts = {}
    for (topic,) in topics_result.all():
        if topic:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
    top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:8]

    # Knowledge gaps
    gaps = (
        (
            await db.execute(
                select(GapCluster)
                .where(GapCluster.workspace_id == ws_id, GapCluster.status == "open")
                .order_by(GapCluster.gap_count.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )

    # Chatbot count
    chatbot_count = (
        await db.execute(
            select(func.count(Chatbot.id)).where(Chatbot.workspace_id == ws_id, Chatbot.archived_at.is_(None))
        )
    ).scalar_one()

    # Recent conversations
    recent_convs = (
        (
            await db.execute(
                select(Conversation)
                .where(Conversation.workspace_id == ws_id)
                .order_by(Conversation.created_at.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )

    user_name = request.state.user.name if request.state.user else "there"
    hour = now.hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    return request.app.state.templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "greeting": greeting,
            "user_name": user_name,
            "total_convs": total_convs,
            "convs_30d": convs_30d,
            "resolution_rate": resolution_rate,
            "escalated": escalated,
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "satisfaction": satisfaction,
            "avg_sentiment": avg_sentiment,
            "top_topics": top_topics,
            "gaps": gaps,
            "chatbot_count": chatbot_count,
            "recent_convs": recent_convs,
        },
    )
