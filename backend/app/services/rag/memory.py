import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversations import Message

ROLE_MAP = {
    "contact": "user",
    "agent": "assistant",
    "bot": "assistant",
    "system": "system",
}


async def get_conversation_history(db: AsyncSession, conversation_id: uuid.UUID, limit: int = 10) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.message_type.in_(["incoming", "outgoing"]),
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))

    history = []
    for msg in messages:
        role = ROLE_MAP.get(msg.author_type, "user")
        if msg.content:
            history.append({"role": role, "content": msg.content})

    return history
