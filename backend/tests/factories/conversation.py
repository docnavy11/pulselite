"""Factories for conversation and message models."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organizational import Workspace
from app.models.knowledge import Chatbot
from app.models.conversations import Conversation, Message


async def make_conversation(
    db: AsyncSession,
    workspace: Workspace,
    chatbot: Chatbot,
    *,
    status: str = "open",
    channel: str = "widget",
    autonomous_resolved: bool = False,
    escalation_reason: str | None = None,
    confidence_avg: float | None = None,
) -> Conversation:
    conv = Conversation(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        chatbot_id=chatbot.id,
        status=status,
        channel=channel,
        autonomous_resolved=autonomous_resolved,
        escalation_reason=escalation_reason,
        confidence_avg=confidence_avg,
    )
    db.add(conv)
    await db.flush()
    return conv


async def make_message(
    db: AsyncSession,
    conversation: Conversation,
    workspace: Workspace,
    *,
    content: str = "Hello, I need help.",
    author_type: str = "user",
    message_type: str = "incoming",
    confidence_score: float | None = None,
) -> Message:
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        workspace_id=workspace.id,
        content=content,
        author_type=author_type,
        message_type=message_type,
        confidence_score=confidence_score,
    )
    db.add(msg)
    await db.flush()
    return msg
