import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversations import Conversation
from app.models.intelligence import GapCluster, GapEvent, RetrievalLog
from app.models.knowledge import Chatbot


async def create_chatbot(db: AsyncSession, workspace_id: uuid.UUID, **kwargs) -> Chatbot:
    chatbot = Chatbot(workspace_id=workspace_id, **kwargs)
    db.add(chatbot)
    await db.flush()
    return chatbot


async def list_chatbots(db: AsyncSession, workspace_id: uuid.UUID) -> list[Chatbot]:
    result = await db.execute(select(Chatbot).where(Chatbot.workspace_id == workspace_id))
    return list(result.scalars().all())


async def get_chatbot(db: AsyncSession, workspace_id: uuid.UUID, chatbot_id: uuid.UUID) -> Chatbot:
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace_id))
    chatbot = result.scalar_one_or_none()
    if chatbot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chatbot not found")
    return chatbot


async def update_chatbot(db: AsyncSession, workspace_id: uuid.UUID, chatbot_id: uuid.UUID, **kwargs) -> Chatbot:
    chatbot = await get_chatbot(db, workspace_id, chatbot_id)
    for key, value in kwargs.items():
        if value is not None:
            setattr(chatbot, key, value)
    await db.flush()
    await db.refresh(chatbot)
    return chatbot


async def delete_chatbot(db: AsyncSession, workspace_id: uuid.UUID, chatbot_id: uuid.UUID) -> None:
    chatbot = await get_chatbot(db, workspace_id, chatbot_id)
    # Delete child records in FK-safe order before deleting chatbot
    # GapEvents reference RetrievalLogs, so delete them first
    retrieval_log_subq = select(RetrievalLog.id).where(RetrievalLog.chatbot_id == chatbot_id).scalar_subquery()
    await db.execute(delete(GapEvent).where(GapEvent.retrieval_log_id.in_(retrieval_log_subq)))
    await db.execute(
        delete(RetrievalLog).where(RetrievalLog.chatbot_id == chatbot_id)
    )
    await db.execute(
        delete(GapCluster).where(GapCluster.chatbot_id == chatbot_id)
    )
    await db.execute(
        update(Conversation)
        .where(Conversation.chatbot_id == chatbot_id)
        .values(chatbot_id=None)
    )
    await db.delete(chatbot)
    await db.flush()
