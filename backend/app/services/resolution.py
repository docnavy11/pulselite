"""Chat resolution service — orchestrates RAG + LLM streaming + actions."""

import asyncio
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence import GapEvent, RetrievalLog
from app.models.knowledge import Chatbot
from app.models.organizational import Workspace
from app.services import conversation_service
from app.services.credits import debit_credits, estimate_token_cost
from app.services.deployment import is_cloud
from app.services.encryption import decrypt_api_key
from app.services.rag import RAGResult, process_query

logger = logging.getLogger(__name__)

_TRIVIAL_PATTERNS = re.compile(
    r"^("
    r"h(i|ey|ello|oi|ola|allo)"
    r"|yo\b"
    r"|good\s*(morning|afternoon|evening|day)"
    r"|goeie?(morgen|middag|avond|dag)"
    r"|bonjour|bonsoir|salut"
    r"|who\s+are\s+you"
    r"|what\s+are\s+you"
    r"|wie\s+ben\s+j(e|ij)"
    r"|how\s+are\s+you"
    r"|hoe\s+gaat\s+het"
    r"|thanks?(\s+you)?"
    r"|thank\s+you"
    r"|bedankt|dank\s*(je|u)"
    r"|merci"
    r"|bye|goodbye|see\s+ya|tot\s+ziens"
    r"|ok(ay)?"
    r"|yes|no|ja|nee|oui|non"
    r"|test(ing)?"
    r"|help"
    r")[\s!?.]*$",
    re.IGNORECASE,
)

MIN_QUERY_LENGTH = 8


def _is_substantive_query(message: str) -> bool:
    stripped = message.strip()
    if len(stripped) < MIN_QUERY_LENGTH:
        return False
    return not _TRIVIAL_PATTERNS.match(stripped)


@dataclass
class ResolutionEvent:
    type: str
    data: Any
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
    openrouter_key = None
    openrouter_base_url = None
    ws_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = ws_result.scalar_one_or_none()
    if ws:
        openrouter_base_url = ws.openrouter_base_url
        if ws.openrouter_api_key:
            try:
                openrouter_key = decrypt_api_key(ws.openrouter_api_key)
            except Exception:
                logger.warning("Failed to decrypt workspace OpenRouter key for %s", workspace_id)

    if is_cloud() and ws:
        if ws.credit_balance <= 0:
            yield ResolutionEvent(type="error", data="Credit balance exhausted")
            return
        if conversation_id is None:
            await conversation_service.check_conversation_cap(ws, db)

    if conversation_id is None:
        conversation = await conversation_service.create_conversation(db, workspace_id, chatbot.id, contact_id)
        conversation_id = conversation.id
        # Fire webhook in background
        from app.services.webhooks import fire_event

        asyncio.create_task(fire_event(workspace_id, "conversation.created", {"conversation_id": str(conversation_id)}))
    else:
        conversation = await conversation_service.get_conversation(db, conversation_id)

    await conversation_service.add_message(
        db, conversation_id, workspace_id, content=message, author_type="contact", message_type="incoming"
    )

    from app.services.action_service import list_enabled_actions

    enabled_actions = await list_enabled_actions(db, workspace_id, chatbot.id)
    actions_with_params = [a for a in enabled_actions if a.parameters]

    rag_result = None
    full_response = ""
    inline_action_payloads = []
    token_usage = None

    try:
        async for item in process_query(
            db,
            message,
            chatbot,
            conversation_id,
            openrouter_key=openrouter_key,
            openrouter_base_url=openrouter_base_url,
            actions=actions_with_params if actions_with_params else None,
        ):
            if isinstance(item, RAGResult):
                rag_result = item
                continue
            if isinstance(item, dict):
                if "prompt_tokens" in item:
                    token_usage = item
                else:
                    inline_action_payloads.append(item)
                continue
            full_response += item
            yield ResolutionEvent(type="token", data=item, conversation_id=conversation_id)
    except Exception as exc:
        error_msg = str(exc).lower()
        if "401" in error_msg or "unauthorized" in error_msg:
            user_error = (
                "AI provider authentication failed. Please check your API key configuration in Settings > AI Models."
            )
        elif "429" in error_msg or "rate" in error_msg:
            user_error = "AI provider rate limit reached. Please try again in a moment."
        elif "timeout" in error_msg or "timed out" in error_msg:
            user_error = "AI provider request timed out. The service may be temporarily unavailable."
        elif "connection" in error_msg or "refused" in error_msg:
            user_error = "Cannot connect to AI provider. Please check that your AI_BASE_URL is correct and the service is running."
        elif "model" in error_msg and ("not found" in error_msg or "does not exist" in error_msg):
            user_error = f"AI model not available. Check your model configuration. Detail: {exc}"
        else:
            user_error = "Something went wrong while generating a response. Please try again."
        logger.error("Chat generation failed for chatbot %s: %s", chatbot.id, exc, exc_info=True)
        yield ResolutionEvent(type="error", data=user_error, conversation_id=conversation_id)
        return

    confidence_score = rag_result.confidence_score if rag_result else 0.0
    confidence_avg = rag_result.confidence_avg if rag_result else 0.0
    escalated = rag_result.escalated if rag_result else False

    if escalated and not _is_substantive_query(message):
        escalated = False

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
        from app.services.webhooks import fire_event

        asyncio.create_task(
            fire_event(workspace_id, "conversation.escalated", {"conversation_id": str(conversation_id)})
        )
    else:
        conversation.autonomous_resolved = True
        conversation.outcome = "resolved_autonomously"

    conversation.confidence_avg = confidence_avg
    conversation.ai_participated = True
    await db.flush()

    if is_cloud() and ws and token_usage:
        total_tokens = token_usage.get("prompt_tokens", 0) + token_usage.get("completion_tokens", 0)
        if total_tokens > 0:
            cost = estimate_token_cost(chatbot.llm_model, total_tokens, is_byok=ws.is_byok)
            try:
                await debit_credits(db, workspace_id, cost, reason=f"chat:{chatbot.llm_model}:{total_tokens}tokens")
            except ValueError:
                logger.warning("Failed to debit %d credits for workspace %s", cost, workspace_id)

    try:
        retrieval_log = RetrievalLog(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            chatbot_id=chatbot.id,
            conversation_id=conversation_id,
            message_id=bot_message.id,
            query=message,
            confidence_score=confidence_score,
            confidence_avg=confidence_avg,
            retrieved_chunk_ids=rag_result.retrieved_chunk_ids if rag_result else [],
            reranked=chatbot.use_reranking,
            escalated=escalated,
            response_generated=True,
        )
        db.add(retrieval_log)
        await db.flush()
        if rag_result and rag_result.original_confidence_low and _is_substantive_query(message):
            gap_event = GapEvent(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                retrieval_log_id=retrieval_log.id,
                query=message,
                confidence_score=confidence_score,
            )
            db.add(gap_event)
            await db.flush()
    except Exception:
        logger.warning("Failed to record retrieval log / gap event", exc_info=True)

    for payload in inline_action_payloads:
        yield ResolutionEvent(type="action", data=payload, conversation_id=conversation_id)

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
