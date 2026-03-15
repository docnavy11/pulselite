import csv
import io
import json
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.conversations import Conversation
from app.models.knowledge import Chatbot
from app.models.organizational import Agent, WorkspaceMembership
from app.schemas.chat import ChatEvent, ChatRequest, ConversationResponse, MessageResponse
from app.services import conversation_service
from app.services.resolution_service import handle_message

router = APIRouter(tags=["chat"])


class MessageFeedbackBody(BaseModel):
    rating: Literal["thumbs_up", "thumbs_down"]
    comment: str | None = None


@router.post("/chat")
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(select(Chatbot).where(Chatbot.id == body.chatbot_id))
    chatbot = result.scalar_one_or_none()
    if chatbot is None:

        async def error_stream():
            yield {"event": "error", "data": json.dumps({"type": "error", "data": "Chatbot not found"})}

        return EventSourceResponse(error_stream())

    workspace_id = chatbot.workspace_id

    membership_result = await db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.agent_id == current_user.id,
        )
    )
    if membership_result.scalar_one_or_none() is None:

        async def forbidden_stream():
            yield {"event": "error", "data": json.dumps({"type": "error", "data": "Not authorized for this workspace"})}

        return EventSourceResponse(forbidden_stream())

    async def event_stream():
        async for event in handle_message(
            db,
            workspace_id,
            chatbot,
            body.message,
            conversation_id=body.conversation_id,
            contact_id=body.contact_id,
        ):
            chat_event = ChatEvent(
                type=event.type,
                data=event.data,
                confidence_score=event.confidence_score,
                confidence_avg=event.confidence_avg,
                escalated=event.escalated,
                conversation_id=event.conversation_id,
                message_id=event.message_id,
            )
            yield {"event": event.type, "data": chat_event.model_dump_json()}

    return EventSourceResponse(event_stream())


@router.get("/workspaces/{workspace_id}/conversations/export")
async def export_conversations_csv(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    stream = await db.stream_scalars(
        select(Conversation)
        .where(Conversation.workspace_id == workspace_id)
        .order_by(Conversation.created_at.desc())
        .execution_options(yield_per=100)
    )

    async def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "chatbot_id",
                "contact_id",
                "status",
                "priority",
                "channel",
                "lifecycle_stage",
                "confidence_avg",
                "outcome",
                "autonomous_resolved",
                "ai_participated",
                "escalation_reason",
                "created_at",
                "updated_at",
            ]
        )
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        async for conv in stream:
            writer.writerow(
                [
                    str(conv.id),
                    str(conv.chatbot_id) if conv.chatbot_id else "",
                    str(conv.contact_id) if conv.contact_id else "",
                    conv.status or "",
                    conv.priority or "",
                    conv.channel or "",
                    conv.lifecycle_stage or "",
                    conv.confidence_avg if conv.confidence_avg is not None else "",
                    conv.outcome or "",
                    conv.autonomous_resolved,
                    conv.ai_participated,
                    conv.escalation_reason or "",
                    conv.created_at.isoformat() if conv.created_at else "",
                    conv.updated_at.isoformat() if conv.updated_at else "",
                ]
            )
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=conversations.csv"},
    )


@router.get("/workspaces/{workspace_id}/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    workspace_id: uuid.UUID = Depends(get_workspace),
    status: str | None = Query(None),
    chatbot_id: uuid.UUID | None = Query(None),
    outcome: str | None = Query(None),
    topic: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    from fastapi import HTTPException, status as http_status

    # Validate date strings before passing to service
    if date_from is not None:
        try:
            datetime.fromisoformat(date_from)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid date_from format"
            )
    if date_to is not None:
        try:
            datetime.fromisoformat(date_to)
        except (ValueError, TypeError):
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid date_to format")
    return await conversation_service.list_conversations(
        db,
        workspace_id,
        status_filter=status,
        chatbot_id=chatbot_id,
        outcome_filter=outcome,
        limit=limit,
        offset=offset,
        date_from=date_from,
        date_to=date_to,
        topic=topic,
    )


@router.get("/workspaces/{workspace_id}/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.get_conversation(db, conversation_id, workspace_id)


@router.get("/workspaces/{workspace_id}/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.get_messages(db, conversation_id, workspace_id, limit)


@router.post(
    "/workspaces/{workspace_id}/conversations/{conversation_id}/messages/{message_id}/feedback", status_code=201
)
async def submit_message_feedback(
    body: MessageFeedbackBody,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    from fastapi import HTTPException
    from app.models.conversations import Message, MessageFeedback

    # Verify the conversation belongs to the workspace
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
        )
    )
    if conv_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify the message belongs to the conversation
    msg_result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conversation_id,
        )
    )
    msg = msg_result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    feedback = MessageFeedback(
        message_id=message_id,
        conversation_id=conversation_id,
        workspace_id=workspace_id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(feedback)
    await db.commit()
    return {"status": "ok"}
