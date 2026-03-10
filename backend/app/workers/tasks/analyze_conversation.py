import asyncio
import json
import logging
import time
import uuid

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.conversations import Conversation, Message
from app.models.intelligence import ConversationAnalysis, IntelligenceSignal
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """Analyze this customer support conversation and extract structured data.
Return a JSON object with exactly these fields:

{
  "sentiment_score": float (-1.0 to 1.0),
  "sentiment_label": "positive" | "neutral" | "negative" | "mixed",
  "intent_primary": string (main intent of the conversation),
  "intent_secondary": string[] (secondary intents),
  "outcome_category": "resolved" | "unresolved" | "escalated" | "abandoned",
  "lead_intent": "none" | "low" | "medium" | "high",
  "feature_requests": string[] (specific features requested),
  "bug_reports": string[] (bugs reported),
  "competitor_mentions": string[] (competitors mentioned by name),
  "expansion_signals": string[] (signals of wanting to expand/upgrade),
  "churn_signals": string[] (signals of wanting to leave/cancel),
  "topics": string[] (main topics discussed),
  "customer_effort_score": float (1-5, estimated from conversation difficulty),
  "summary": string (2-sentence summary),
  "action_items": string[] (recommended follow-up actions)
}

Conversation transcript:
"""


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def analyze_conversation(self, conversation_id: str, workspace_id: str) -> dict:
    try:
        return asyncio.run(_analyze(uuid.UUID(conversation_id), uuid.UUID(workspace_id)))
    except Exception as exc:
        self.retry(exc=exc)


async def _analyze(conversation_id: uuid.UUID, workspace_id: uuid.UUID) -> dict:
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
            )
            messages = result.scalars().all()

            if not messages:
                return {"status": "skipped", "reason": "no messages"}

            transcript = _build_transcript(messages)
            analysis_data = await _call_llm(transcript)
            start_time = time.monotonic()

            analysis = ConversationAnalysis(
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                sentiment_score=analysis_data.get("sentiment_score"),
                sentiment_label=analysis_data.get("sentiment_label"),
                intent_primary=analysis_data.get("intent_primary"),
                intent_secondary=analysis_data.get("intent_secondary"),
                outcome_category=analysis_data.get("outcome_category"),
                lead_intent=analysis_data.get("lead_intent"),
                feature_requests=analysis_data.get("feature_requests"),
                bug_reports=analysis_data.get("bug_reports"),
                competitor_mentions=analysis_data.get("competitor_mentions"),
                expansion_signals=analysis_data.get("expansion_signals"),
                churn_signals=analysis_data.get("churn_signals"),
                topics=analysis_data.get("topics"),
                customer_effort_score=analysis_data.get("customer_effort_score"),
                summary=analysis_data.get("summary"),
                action_items=analysis_data.get("action_items"),
                processing_ms=int((time.monotonic() - start_time) * 1000),
            )
            session.add(analysis)

            contact_id = await _get_contact_id(session, conversation_id)
            await _fan_out_signals(session, workspace_id, conversation_id, contact_id, analysis_data)

            await session.commit()
            return {"status": "success", "conversation_id": str(conversation_id)}
        except Exception:
            await session.rollback()
            raise


def _build_transcript(messages: list[Message]) -> str:
    lines = []
    for msg in messages:
        role = msg.author_type.upper()
        content = msg.content or "[no content]"
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def _call_llm(transcript: str) -> dict:
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert conversation analyst. Always respond with valid JSON."},
            {"role": "user", "content": ANALYSIS_PROMPT + transcript},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2000,
    )
    return json.loads(response.choices[0].message.content)


async def _get_contact_id(session: AsyncSession, conversation_id: uuid.UUID) -> uuid.UUID | None:
    result = await session.execute(select(Conversation.contact_id).where(Conversation.id == conversation_id))
    row = result.one_or_none()
    return row[0] if row else None


async def _fan_out_signals(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    contact_id: uuid.UUID | None,
    data: dict,
) -> None:
    for feature in data.get("feature_requests", []):
        session.add(
            IntelligenceSignal(
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                contact_id=contact_id,
                signal_type="feature_request",
                payload={"feature": feature},
            )
        )

    for bug in data.get("bug_reports", []):
        session.add(
            IntelligenceSignal(
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                contact_id=contact_id,
                signal_type="bug_report",
                payload={"bug": bug},
            )
        )

    for competitor in data.get("competitor_mentions", []):
        session.add(
            IntelligenceSignal(
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                contact_id=contact_id,
                signal_type="competitor_mention",
                payload={"competitor": competitor},
            )
        )

    for signal in data.get("churn_signals", []):
        session.add(
            IntelligenceSignal(
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                contact_id=contact_id,
                signal_type="churn_risk",
                payload={"signal": signal},
            )
        )

    for signal in data.get("expansion_signals", []):
        session.add(
            IntelligenceSignal(
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                contact_id=contact_id,
                signal_type="expansion_opportunity",
                payload={"signal": signal},
            )
        )

    lead_intent = data.get("lead_intent", "none")
    if lead_intent in ("medium", "high"):
        session.add(
            IntelligenceSignal(
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                contact_id=contact_id,
                signal_type="lead_hot" if lead_intent == "high" else "lead_warm",
                payload={"lead_intent": lead_intent},
            )
        )
