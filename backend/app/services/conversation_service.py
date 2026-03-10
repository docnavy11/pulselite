import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversations import Conversation, Message


async def create_conversation(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    contact_id: uuid.UUID | None = None,
    channel: str = "chat",
) -> Conversation:
    conversation = Conversation(
        workspace_id=workspace_id,
        chatbot_id=chatbot_id,
        contact_id=contact_id,
        channel=channel,
        status="open",
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def get_conversation(
    db: AsyncSession, conversation_id: uuid.UUID, workspace_id: uuid.UUID | None = None
) -> Conversation:
    query = select(Conversation).options(selectinload(Conversation.messages)).where(Conversation.id == conversation_id)
    if workspace_id is not None:
        query = query.where(Conversation.workspace_id == workspace_id)
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


async def add_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID,
    content: str,
    author_type: str,
    message_type: str,
    author_id: uuid.UUID | None = None,
    confidence_score: float | None = None,
    retrieval_log_id: uuid.UUID | None = None,
    is_fallback: bool = False,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        workspace_id=workspace_id,
        content=content,
        author_type=author_type,
        message_type=message_type,
        author_id=author_id,
        confidence_score=confidence_score,
        retrieval_log_id=retrieval_log_id,
        is_fallback=is_fallback,
    )
    db.add(message)
    await db.flush()
    return message


async def list_conversations(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    status_filter: str | None = None,
    chatbot_id: uuid.UUID | None = None,
    outcome_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Conversation]:
    query = select(Conversation).where(Conversation.workspace_id == workspace_id)
    if status_filter:
        query = query.where(Conversation.status == status_filter)
    if chatbot_id:
        query = query.where(Conversation.chatbot_id == chatbot_id)
    if outcome_filter:
        query = query.where(Conversation.outcome == outcome_filter)
    if date_from:
        query = query.where(Conversation.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.where(Conversation.created_at < datetime.fromisoformat(date_to) + timedelta(days=1))
    query = query.order_by(Conversation.updated_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID,
    limit: int = 100,
) -> list[Message]:
    # First verify the conversation belongs to this workspace (prevents IDOR)
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
        )
    )
    conversation = conv_result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    result = await db.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.workspace_id == workspace_id,
        )
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_conversation_status(
    db: AsyncSession, conversation_id: uuid.UUID, new_status: str, workspace_id: uuid.UUID | None = None
) -> Conversation:
    query = select(Conversation).where(Conversation.id == conversation_id)
    if workspace_id is not None:
        query = query.where(Conversation.workspace_id == workspace_id)
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    conversation.status = new_status
    await db.flush()
    return conversation
