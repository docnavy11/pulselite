import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
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


def _validate_session_id(value: str) -> str:
    """Validate that session_id is a valid UUID (max 128 chars)."""
    if len(value) > 128:
        raise ValueError("session_id exceeds maximum length of 128 characters")
    try:
        uuid.UUID(value)
    except ValueError:
        raise ValueError("session_id must be a valid UUID")
    return value


class LeadCapture(BaseModel):
    chatbot_id: uuid.UUID
    session_id: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        return _validate_session_id(v)


class PublicChatRequest(BaseModel):
    chatbot_id: uuid.UUID
    session_id: str
    message: str

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        return _validate_session_id(v)


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

    async def event_stream():
        async for event in handle_message(
            db,
            workspace_id,
            chatbot,
            body.message,
            contact_id=contact.id,
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
            await _fire_lead_notifications(db, chatbot, body)
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

    await _fire_lead_notifications(db, chatbot, body)
    return {"status": "created"}


async def _fire_lead_notifications(db: AsyncSession, chatbot: "Chatbot", body: "LeadCapture") -> None:
    """Fire webhook/slack actions with lead data after form submission (fire-and-forget)."""
    import asyncio as _asyncio
    import uuid as _uuid
    from app.services.action_executor import execute_action, _get_workspace_slack_webhook
    from app.services.action_service import list_enabled_actions
    from app.models.actions import ActionEvent

    actions = await list_enabled_actions(db, chatbot.workspace_id, chatbot.id)
    notifiable = [a for a in actions if a.action_type in ("webhook", "slack_message")]
    if not notifiable:
        return

    slack_webhook = await _get_workspace_slack_webhook(db, chatbot.workspace_id)
    context = {
        "event": "lead.submit",
        "name": body.name or "",
        "email": body.email or "",
        "phone": body.phone or "",
        "session_id": body.session_id,
    }

    async def _run() -> None:
        for action in notifiable:
            status, _ = await execute_action(action, context, slack_webhook)
            event = ActionEvent(
                id=_uuid.uuid4(),
                workspace_id=chatbot.workspace_id,
                chatbot_id=chatbot.id,
                conversation_id=None,
                action_id=action.id,
                action_type=action.action_type,
                payload=context,
                status=status,
            )
            db.add(event)
        await db.commit()

    _asyncio.create_task(_run())


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
