import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Chatbot
from app.models.organizational import Workspace
from app.services.encryption import decrypt_api_key
from app.services import conversation_service
from app.services.rag.engine import RAGResult, process_query
from app.services.webhooks import fire_event

logger = logging.getLogger(__name__)


@dataclass
class ResolutionEvent:
    type: str  # "token" | "done" | "error" | "action"
    data: Any  # str for tokens, dict for action events
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
        asyncio.create_task(fire_event(
            db,
            workspace_id,
            "conversation.created",
            {
                "conversation_id": str(conversation_id),
            },
        ))
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

    # Load workspace OpenRouter key if configured
    openrouter_key: str | None = None
    ws_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = ws_result.scalar_one_or_none()
    if ws and ws.openrouter_api_key:
        try:
            openrouter_key = decrypt_api_key(ws.openrouter_api_key)
        except Exception:
            logger.warning(f"Failed to decrypt workspace OpenRouter key for {workspace_id}")

    # Load enabled actions — those with parameters use function calling; others use post-response trigger
    from app.services.action_service import list_enabled_actions
    enabled_actions = await list_enabled_actions(db, workspace_id, chatbot.id)
    actions_with_params = [a for a in enabled_actions if a.parameters]

    rag_result: RAGResult | None = None
    full_response = ""
    inline_action_payloads: list[dict] = []

    async for item in process_query(
        db, message, chatbot, conversation_id,
        openrouter_key=openrouter_key,
        actions=actions_with_params if actions_with_params else None,
    ):
        if isinstance(item, RAGResult):
            rag_result = item
            continue
        if isinstance(item, dict):
            # Triggered action payload (client-side) from function calling
            inline_action_payloads.append(item)
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
        asyncio.create_task(fire_event(
            db,
            workspace_id,
            "conversation.escalated",
            {
                "conversation_id": str(conversation_id),
            },
        ))
    else:
        conversation.autonomous_resolved = True
        conversation.outcome = "resolved_autonomously"

    conversation.confidence_avg = confidence_avg
    conversation.ai_participated = True
    await db.flush()

    # Yield function-call-triggered action payloads (from actions with parameters)
    for payload in inline_action_payloads:
        yield ResolutionEvent(type="action", data=payload, conversation_id=conversation_id)

    # Post-response: fire actions WITHOUT parameters (LLM yes/no trigger path)
    try:
        from app.services.action_executor import run_actions
        actions_without_params = [a for a in enabled_actions if not a.parameters]
        if actions_without_params:
            client_payloads = await run_actions(
                db_session=db,
                workspace_id=workspace_id,
                chatbot_id=chatbot.id,
                conversation_id=conversation_id,
                user_message=message,
                bot_response=full_response,
            )
            for payload in client_payloads:
                yield ResolutionEvent(type="action", data=payload, conversation_id=conversation_id)
    except Exception:
        logger.exception("Action execution failed — continuing without actions")

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
