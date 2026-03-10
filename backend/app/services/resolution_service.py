import logging
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Chatbot
from app.models.organizational import Workspace
from app.services.encryption import decrypt_api_key
from app.services import conversation_service
from app.services.rag.engine import RAGResult, process_query
from app.services.webhooks import fire_event
from app.workers.tasks.log_retrieval import log_retrieval_task
from app.workers.tasks.score_lead import flush_lead_score, score_lead_message
from app.workers.tasks.send_alerts import send_escalation_alerts

logger = logging.getLogger(__name__)


@dataclass
class ResolutionEvent:
    type: str  # "token" | "done" | "error" | "action"
    data: str
    confidence_score: float | None = None
    confidence_avg: float | None = None
    escalated: bool = False
    conversation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    sources: list[dict] | None = None


async def handle_message(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    chatbot: Chatbot,
    message: str,
    conversation_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
) -> AsyncGenerator[ResolutionEvent, None]:
    if conversation_id is None:
        conversation = await conversation_service.create_conversation(db, workspace_id, chatbot.id, contact_id)
        conversation_id = conversation.id
        await fire_event(
            db,
            workspace_id,
            "conversation.created",
            {
                "conversation_id": str(conversation_id),
            },
        )
    else:
        conversation = await conversation_service.get_conversation(db, conversation_id)

    await conversation_service.add_message(
        db,
        conversation_id,
        workspace_id,
        content=message,
        author_type="contact",
        message_type="incoming",
    )

    score_lead_message.delay(str(conversation_id), message)

    # Load workspace OpenRouter key if configured
    openrouter_key: str | None = None
    ws_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = ws_result.scalar_one_or_none()
    if ws and ws.openrouter_api_key:
        try:
            openrouter_key = decrypt_api_key(ws.openrouter_api_key)
        except Exception:
            logger.warning(f"Failed to decrypt workspace OpenRouter key for {workspace_id}")

    rag_result: RAGResult | None = None
    full_response = ""

    async for item in process_query(db, message, chatbot, conversation_id, openrouter_key=openrouter_key):
        if isinstance(item, RAGResult):
            rag_result = item
            continue
        full_response += item
        yield ResolutionEvent(type="token", data=item, conversation_id=conversation_id)

    confidence_score = rag_result.confidence_score if rag_result else 0.0
    confidence_avg = rag_result.confidence_avg if rag_result else 0.0
    escalated = rag_result.escalated if rag_result else False

    bot_message = await conversation_service.add_message(
        db,
        conversation_id,
        workspace_id,
        content=full_response,
        author_type="bot",
        message_type="outgoing",
        confidence_score=confidence_score,
        is_fallback=escalated,
    )

    if escalated:
        conversation.escalation_reason = "low_confidence"
        conversation.outcome = "escalated_to_human"
        send_escalation_alerts.delay(str(conversation_id), str(workspace_id))
        await fire_event(
            db,
            workspace_id,
            "conversation.escalated",
            {
                "conversation_id": str(conversation_id),
            },
        )
    else:
        conversation.autonomous_resolved = True
        conversation.outcome = "resolved_autonomously"

    conversation.confidence_avg = confidence_avg
    conversation.ai_participated = True
    await db.flush()

    # Flush accumulated lead score to DB and trigger HubSpot push if hot
    if contact_id:
        flush_lead_score.delay(str(conversation_id), str(workspace_id))  # type: ignore[attr-defined]

    if rag_result:
        log_retrieval_task.delay(
            workspace_id=str(workspace_id),
            chatbot_id=str(chatbot.id),
            conversation_id=str(conversation_id),
            message_id=str(bot_message.id),
            query=rag_result.query,
            confidence_score=rag_result.confidence_score,
            confidence_avg=rag_result.confidence_avg,
            retrieved_chunk_ids=[str(cid) for cid in rag_result.retrieved_chunk_ids],
            escalated=rag_result.escalated,
        )

    sources = rag_result.sources if rag_result else []
    yield ResolutionEvent(
        type="done",
        data="",
        confidence_score=confidence_score,
        confidence_avg=confidence_avg,
        escalated=escalated,
        conversation_id=conversation_id,
        message_id=bot_message.id,
        sources=sources,
    )
