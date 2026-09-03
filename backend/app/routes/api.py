"""JSON-only API endpoints — for the widget, public chat, and Preact islands."""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models.knowledge import Chatbot
from app.models.contacts import Contact
from app.services.resolution import ResolutionEvent, handle_message

router = APIRouter(prefix="/api")


@router.get("/widget/{chatbot_id}/config")
async def widget_config(chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.is_active == True))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    return {
        "chatbot_id": str(chatbot.id), "name": chatbot.name, "display_name": chatbot.display_name,
        "welcome_message": chatbot.welcome_message, "suggested_questions": chatbot.suggested_questions or [],
        "brand_color": chatbot.brand_color, "widget_config": chatbot.widget_config or {},
    }


class ChatRequest(BaseModel):
    chatbot_id: uuid.UUID
    message: str
    conversation_id: uuid.UUID | None = None
    session_id: str | None = None


@router.post("/chat")
async def public_chat(body: ChatRequest, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Chatbot).where(Chatbot.id == body.chatbot_id, Chatbot.is_active == True))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    # Resolve or create contact
    contact_id = None
    if body.session_id:
        contact_result = await db.execute(
            select(Contact).where(Contact.workspace_id == chatbot.workspace_id, Contact.external_id == body.session_id)
        )
        contact = contact_result.scalar_one_or_none()
        if not contact:
            contact = Contact(workspace_id=chatbot.workspace_id, external_id=body.session_id, contact_type="visitor")
            db.add(contact)
            await db.flush()
        contact_id = contact.id

    async def event_stream():
        async for event in handle_message(
            db, chatbot.workspace_id, chatbot, body.message,
            conversation_id=body.conversation_id, contact_id=contact_id,
        ):
            if event.type == "token":
                yield {"event": "token", "data": event.data}
            elif event.type == "done":
                yield {"event": "done", "data": json.dumps({
                    "conversation_id": str(event.conversation_id) if event.conversation_id else None,
                    "message_id": str(event.message_id) if event.message_id else None,
                    "confidence_score": event.confidence_score,
                    "escalated": event.escalated,
                    "sources": event.sources or [],
                })}
            elif event.type == "error":
                yield {"event": "error", "data": event.data}
            elif event.type == "action":
                yield {"event": "action", "data": json.dumps(event.data)}

    return EventSourceResponse(event_stream())


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/config/deployment")
async def deployment_config():
    from app.config import settings
    return {"cloud_mode": settings.CLOUD_MODE}
