import asyncio
import json
import logging
import time
import uuid
from collections.abc import Sequence

from openai import AsyncOpenAI
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory, engine
from app.models.conversations import Message
from app.models.intelligence import ConversationAnalysis
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
  "topics": string[] (main topics discussed),
  "summary": string (2-sentence summary)
}

Conversation transcript:
"""


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def analyze_conversation(self, conversation_id: str, workspace_id: str) -> dict:
    try:
        return asyncio.run(_analyze(uuid.UUID(conversation_id), uuid.UUID(workspace_id)))
    except Exception as exc:
        raise self.retry(exc=exc)  # type: ignore[attr-defined]


async def _analyze(conversation_id: uuid.UUID, workspace_id: uuid.UUID) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
            )
            messages = list(result.scalars().all())

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
                topics=analysis_data.get("topics"),
                summary=analysis_data.get("summary"),
                processing_ms=int((time.monotonic() - start_time) * 1000),
            )
            session.add(analysis)

            await session.commit()
            return {"status": "success", "conversation_id": str(conversation_id)}
        except Exception:
            await session.rollback()
            raise


def _build_transcript(messages: Sequence[Message]) -> str:
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
    return json.loads(response.choices[0].message.content or "{}")


