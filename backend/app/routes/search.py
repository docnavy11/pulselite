"""Global search — powers the ⌘K command palette."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.conversations import Conversation
from app.models.knowledge import Chatbot

router = APIRouter()


@router.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = "", db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    q = q.strip()

    chatbots = []
    conversations = []

    if q and len(q) >= 1:
        chatbots = (
            (
                await db.execute(
                    select(Chatbot)
                    .where(Chatbot.workspace_id == workspace.id, Chatbot.archived_at.is_(None))
                    .where(Chatbot.name.ilike(f"%{q}%"))
                    .limit(5)
                )
            )
            .scalars()
            .all()
        )

        conversations = (
            (
                await db.execute(
                    select(Conversation)
                    .where(Conversation.workspace_id == workspace.id)
                    .where(Conversation.last_message_preview.ilike(f"%{q}%"))
                    .order_by(Conversation.created_at.desc())
                    .limit(5)
                )
            )
            .scalars()
            .all()
        )

    return request.app.state.templates.TemplateResponse(
        "components/search_results.html",
        {"request": request, "q": q, "chatbots": chatbots, "conversations": conversations},
    )
