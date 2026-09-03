"""Dashboard route."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.conversations import Conversation, MessageFeedback
from app.models.knowledge import Chatbot

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Total conversations (30d)
    conv_count = (await db.execute(
        select(func.count(Conversation.id)).where(
            Conversation.workspace_id == workspace.id, Conversation.created_at >= thirty_days_ago,
        )
    )).scalar_one()

    # Resolution rate
    resolved = (await db.execute(
        select(func.count(Conversation.id)).where(
            Conversation.workspace_id == workspace.id, Conversation.created_at >= thirty_days_ago,
            Conversation.autonomous_resolved == True,
        )
    )).scalar_one()
    resolution_rate = (resolved / conv_count * 100) if conv_count > 0 else 0

    # Chatbot count
    chatbot_count = (await db.execute(
        select(func.count(Chatbot.id)).where(Chatbot.workspace_id == workspace.id, Chatbot.archived_at.is_(None))
    )).scalar_one()

    # Feedback counts
    thumbs_up = (await db.execute(
        select(func.count(MessageFeedback.id)).where(
            MessageFeedback.workspace_id == workspace.id, MessageFeedback.rating == "thumbs_up",
            MessageFeedback.created_at >= thirty_days_ago,
        )
    )).scalar_one()
    thumbs_down = (await db.execute(
        select(func.count(MessageFeedback.id)).where(
            MessageFeedback.workspace_id == workspace.id, MessageFeedback.rating == "thumbs_down",
            MessageFeedback.created_at >= thirty_days_ago,
        )
    )).scalar_one()

    return request.app.state.templates.TemplateResponse("dashboard/index.html", {
        "request": request,
        "stats": {
            "conversations_30d": conv_count, "resolution_rate": round(resolution_rate, 1),
            "chatbot_count": chatbot_count, "thumbs_up": thumbs_up, "thumbs_down": thumbs_down,
        },
    })
