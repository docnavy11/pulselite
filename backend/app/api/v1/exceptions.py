import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.contacts import Company, Contact
from app.models.conversations import Conversation, Message
from app.models.knowledge import Chatbot
from app.models.organizational import Agent
from app.schemas.exceptions import (
    ContactContext,
    ExceptionConversation,
    ExceptionDetailResponse,
    ExceptionListResponse,
    ExceptionReplyRequest,
    MessageDetail,
)
from app.services.suggestion_service import get_suggested_action

router = APIRouter(tags=["exceptions"])


@router.get(
    "/workspaces/{workspace_id}/exceptions",
    response_model=ExceptionListResponse,
)
async def list_exceptions(
    workspace_id: uuid.UUID = Depends(get_workspace),
    escalation_reason: str | None = None,
    chatbot_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    base_filter = [
        Conversation.workspace_id == workspace_id,
        Conversation.status == "open",
        or_(
            Conversation.escalation_reason.isnot(None),
            Conversation.autonomous_resolved == False,  # noqa: E712
        ),
    ]

    if escalation_reason:
        base_filter.append(Conversation.escalation_reason == escalation_reason)
    if chatbot_id:
        base_filter.append(Conversation.chatbot_id == chatbot_id)
    if date_from:
        base_filter.append(Conversation.created_at >= date_from)
    if date_to:
        base_filter.append(Conversation.created_at <= date_to)

    count_query = select(func.count()).select_from(Conversation).where(*base_filter)
    total = (await db.execute(count_query)).scalar() or 0

    query = (
        select(Conversation).where(*base_filter).order_by(Conversation.created_at.desc()).limit(limit).offset(offset)
    )
    result = await db.execute(query)
    conversations = list(result.scalars().all())

    if not conversations:
        return ExceptionListResponse(items=[], total=total)

    conv_ids = [c.id for c in conversations]
    chatbot_ids = list({c.chatbot_id for c in conversations if c.chatbot_id})
    contact_ids = list({c.contact_id for c in conversations if c.contact_id})

    # Batch fetch chatbot names
    chatbot_map: dict = {}
    if chatbot_ids:
        cb_rows = await db.execute(select(Chatbot.id, Chatbot.name).where(Chatbot.id.in_(chatbot_ids)))
        chatbot_map = {row[0]: row[1] for row in cb_rows.all()}

    # Batch fetch contact info
    contact_map: dict = {}
    if contact_ids:
        ct_rows = await db.execute(select(Contact.id, Contact.name, Contact.email).where(Contact.id.in_(contact_ids)))
        contact_map = {row[0]: (row[1], row[2]) for row in ct_rows.all()}

    # Batch fetch last message per conversation (max created_at subquery)
    latest_msg_subq = (
        select(
            Message.conversation_id,
            func.max(Message.created_at).label("latest_at"),
        )
        .where(Message.conversation_id.in_(conv_ids))
        .group_by(Message.conversation_id)
        .subquery()
    )
    last_msg_rows = await db.execute(
        select(Message.conversation_id, Message.content).join(
            latest_msg_subq,
            (Message.conversation_id == latest_msg_subq.c.conversation_id)
            & (Message.created_at == latest_msg_subq.c.latest_at),
        )
    )
    last_msg_map: dict = {row[0]: row[1] for row in last_msg_rows.all()}

    items = []
    for conv in conversations:
        contact_info = contact_map.get(conv.contact_id, (None, None)) if conv.contact_id else (None, None)
        last_content = last_msg_map.get(conv.id)
        items.append(
            ExceptionConversation(
                id=conv.id,
                workspace_id=conv.workspace_id,
                chatbot_id=conv.chatbot_id,
                chatbot_name=chatbot_map.get(conv.chatbot_id) if conv.chatbot_id else None,
                contact_id=conv.contact_id,
                contact_name=contact_info[0],
                contact_email=contact_info[1],
                escalation_reason=conv.escalation_reason,
                confidence_avg=conv.confidence_avg,
                status=conv.status,
                last_message_preview=last_content[:200] if last_content else None,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        )

    return ExceptionListResponse(items=items, total=total)


@router.get(
    "/workspaces/{workspace_id}/exceptions/{conversation_id}",
    response_model=ExceptionDetailResponse,
)
async def get_exception_detail(
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    chatbot_name = None
    if conv.chatbot_id:
        cb_result = await db.execute(select(Chatbot.name).where(Chatbot.id == conv.chatbot_id))
        row = cb_result.first()
        chatbot_name = row[0] if row else None

    contact_name = None
    contact_email = None
    if conv.contact_id:
        contact_result = await db.execute(select(Contact.name, Contact.email).where(Contact.id == conv.contact_id))
        contact_row = contact_result.first()
        if contact_row:
            contact_name, contact_email = contact_row

    last_msg_result = await db.execute(
        select(Message.content).where(Message.conversation_id == conv.id).order_by(Message.created_at.desc()).limit(1)
    )
    last_msg_row = last_msg_result.first()
    last_message_preview = last_msg_row[0][:200] if last_msg_row and last_msg_row[0] else None

    conversation_data = ExceptionConversation(
        id=conv.id,
        workspace_id=conv.workspace_id,
        chatbot_id=conv.chatbot_id,
        chatbot_name=chatbot_name,
        contact_id=conv.contact_id,
        contact_name=contact_name,
        contact_email=contact_email,
        escalation_reason=conv.escalation_reason,
        confidence_avg=conv.confidence_avg,
        status=conv.status,
        last_message_preview=last_message_preview,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )

    msgs_result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
    )
    messages = [
        MessageDetail(
            id=m.id,
            content=m.content,
            author_type=m.author_type,
            confidence_score=m.confidence_score,
            created_at=m.created_at,
        )
        for m in msgs_result.scalars().all()
    ]

    contact_context = None
    if conv.contact_id:
        contact_result = await db.execute(select(Contact).where(Contact.id == conv.contact_id))
        contact = contact_result.scalar_one_or_none()
        if contact:
            company_name = None
            if contact.company_id:
                company_result = await db.execute(select(Company.name).where(Company.id == contact.company_id))
                company_row = company_result.first()
                company_name = company_row[0] if company_row else None

            prev_count_result = await db.execute(
                select(func.count())
                .select_from(Conversation)
                .where(
                    Conversation.contact_id == conv.contact_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.id != conversation_id,
                )
            )
            prev_count = prev_count_result.scalar() or 0

            contact_context = ContactContext(
                id=contact.id,
                name=contact.name,
                email=contact.email,
                lead_score=contact.lead_score,
                lead_tier=contact.lead_tier,
                company_name=company_name,
                previous_conversations_count=prev_count,
            )

    message_dicts = (
        [{"author_type": m.author_type, "content": m.content} for m in msgs_result.scalars().all()]
        if not messages
        else [{"author_type": m.author_type, "content": m.content} for m in messages]
    )

    suggested_action = await get_suggested_action(
        conversation_id=conversation_id,
        escalation_reason=conv.escalation_reason,
        messages=message_dicts,
    )

    return ExceptionDetailResponse(
        conversation=conversation_data,
        messages=messages,
        contact_context=contact_context,
        suggested_action=suggested_action,
    )


@router.post(
    "/workspaces/{workspace_id}/exceptions/{conversation_id}/reply",
    status_code=status.HTTP_201_CREATED,
)
async def reply_to_exception(
    conversation_id: uuid.UUID,
    body: ExceptionReplyRequest,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    message = Message(
        conversation_id=conversation_id,
        workspace_id=workspace_id,
        content=body.content,
        author_type="agent",
        message_type="comment",
        author_id=current_user.id,
    )
    db.add(message)

    if body.resolve:
        conv.status = "resolved"
        conv.resolved_at = func.now()
        conv.outcome = "resolved_by_agent"

    await db.commit()
    return {"status": "ok", "message_id": str(message.id), "resolved": body.resolve}


@router.post(
    "/workspaces/{workspace_id}/exceptions/{conversation_id}/resolve",
)
async def resolve_exception(
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    conv.status = "resolved"
    conv.resolved_at = func.now()
    conv.outcome = "resolved_by_agent"
    conv.assignee_id = current_user.id
    await db.commit()
    return {"status": "ok", "conversation_id": str(conversation_id)}
