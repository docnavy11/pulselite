import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models.contacts import Contact
from app.models.knowledge import Chatbot
from app.schemas.chat import ChatEvent
from app.schemas.widget import WidgetConfig
from app.services.resolution_service import handle_message

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(tags=["public_chat"])


class LeadCapture(BaseModel):
    chatbot_id: uuid.UUID
    session_id: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None


class PublicChatRequest(BaseModel):
    chatbot_id: uuid.UUID
    session_id: str
    message: str


@router.post("/public/chat")
@limiter.limit("20/minute")
async def public_chat(
    request: Request,
    body: PublicChatRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chatbot).where(Chatbot.id == body.chatbot_id, Chatbot.is_active == True)  # noqa: E712
    )
    chatbot = result.scalar_one_or_none()
    if chatbot is None:

        async def error_stream():
            yield {"event": "error", "data": json.dumps({"type": "error", "data": "Chatbot not found"})}

        return EventSourceResponse(error_stream())

    # Domain restriction check
    widget_cfg = chatbot.widget_config or {}
    parsed_cfg = WidgetConfig(**widget_cfg) if widget_cfg else WidgetConfig()
    allowed = parsed_cfg.allowed_domains
    if allowed:
        origin = request.headers.get("origin", "")
        hostname = re.sub(r"^https?://", "", origin).split(":")[0].split("/")[0]
        if not any(hostname == d.strip() or hostname.endswith("." + d.strip()) for d in allowed if d.strip()):
            raise HTTPException(status_code=403, detail="Origin not allowed")

    workspace_id = chatbot.workspace_id

    contact = await _get_or_create_contact(db, workspace_id, body.session_id)

    # Resolve client IP (respect X-Forwarded-For for proxied deployments)
    forwarded_for = request.headers.get("X-Forwarded-For")
    client_ip = (
        forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else None)
    )

    async def event_stream():
        async for event in handle_message(
            db,
            workspace_id,
            chatbot,
            body.message,
            contact_id=contact.id,
            client_ip=client_ip,
        ):
            chat_event = ChatEvent(
                type=event.type,
                data=event.data,
                confidence_score=event.confidence_score,
                confidence_avg=event.confidence_avg,
                escalated=event.escalated,
                conversation_id=event.conversation_id,
                message_id=event.message_id,
                sources=event.sources or [],
            )
            yield {"event": event.type, "data": chat_event.model_dump_json()}

    return EventSourceResponse(event_stream())


@router.post("/public/chat/lead")
@limiter.limit("10/minute")
async def capture_lead(
    request: Request,
    body: LeadCapture,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Chatbot).where(Chatbot.id == body.chatbot_id, Chatbot.is_active == True))  # noqa: E712
    chatbot = result.scalar_one_or_none()
    if chatbot is None:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    if body.email:
        existing = await db.execute(
            select(Contact).where(
                Contact.workspace_id == chatbot.workspace_id,
                Contact.email == body.email,
            )
        )
        if existing.scalar_one_or_none():
            return {"status": "existing"}

    contact = Contact(
        workspace_id=chatbot.workspace_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        contact_type="lead",
        external_id=body.session_id,
    )
    db.add(contact)
    await db.commit()
    return {"status": "created"}


async def _get_or_create_contact(db: AsyncSession, workspace_id: uuid.UUID, session_id: str) -> Contact:
    result = await db.execute(
        select(Contact).where(
            Contact.workspace_id == workspace_id,
            Contact.external_id == session_id,
        )
    )
    contact = result.scalar_one_or_none()
    if contact:
        return contact

    contact = Contact(
        workspace_id=workspace_id,
        external_id=session_id,
        contact_type="visitor",
        name=f"Visitor {session_id[:8]}",
    )
    db.add(contact)
    await db.flush()
    return contact
