import json
import logging
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.knowledge import Chatbot
from app.models.organizational import Workspace
from app.services.encryption import decrypt_api_key
from app.services import conversation_service
from app.services.action_service import build_tools_for_chatbot, execute_action, list_actions
from app.services.geoip import get_country
from app.services.rag.engine import RAGResult, process_query
from app.services.webhooks import fire_event
from app.workers.tasks.log_retrieval import log_retrieval_task
from app.workers.tasks.score_lead import flush_lead_score, score_lead_message
from app.workers.tasks.send_alerts import send_escalation_alerts

_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

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


async def _detect_and_fire_actions(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    chatbot: Chatbot,
    message: str,
    conversation_id: uuid.UUID | None,
) -> AsyncGenerator[ResolutionEvent, None]:
    """Make a non-streaming OpenAI call with tools to detect and fire actions."""
    actions = await list_actions(db, chatbot.id)
    if not actions:
        return

    tools = build_tools_for_chatbot(actions)
    if not tools:
        return

    try:
        response = await _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant. Determine if any of the provided tools "
                        "should be triggered based on the user message. Only call a tool if "
                        "you are confident the user intent matches the trigger description."
                    ),
                },
                {"role": "user", "content": message},
            ],
            tools=tools,
            tool_choice="auto",
            max_tokens=200,
        )

        if response.choices and response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                fn_name = tool_call.function.name
                if fn_name.startswith("action_"):
                    action_id_str = fn_name[len("action_") :].replace("_", "-")
                    matched = next((a for a in actions if str(a.id) == action_id_str), None)
                    if matched:
                        args = json.loads(tool_call.function.arguments or "{}")
                        action_data = await execute_action(db, workspace_id, chatbot.id, conversation_id, matched, args)
                        yield ResolutionEvent(
                            type="action",
                            data=json.dumps(action_data),
                            conversation_id=conversation_id,
                        )
    except Exception as e:
        logger.error(f"Action detection failed: {e}")


async def handle_message(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    chatbot: Chatbot,
    message: str,
    conversation_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    client_ip: str | None = None,
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
        # Geolocate client IP and store on the conversation (best-effort, non-blocking)
        if client_ip:
            try:
                country_code, country_name = await get_country(client_ip)
                if country_code:
                    conversation.country_code = country_code
                    conversation.country_name = country_name
            except Exception:
                pass
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

    # Detect and fire AI actions before streaming the response
    async for action_event in _detect_and_fire_actions(db, workspace_id, chatbot, message, conversation_id):
        yield action_event

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
