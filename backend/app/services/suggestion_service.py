import logging
import uuid

import redis

from app.config import settings
from app.services.llm import get_llm_client

logger = logging.getLogger(__name__)

CACHE_TTL = 3600  # 1 hour


def _get_redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_suggested_action(
    conversation_id: uuid.UUID,
    escalation_reason: str | None,
    messages: list[dict],
) -> str | None:
    cache_key = f"pulse:suggestion:{conversation_id}"

    r = _get_redis()
    cached = r.get(cache_key)
    if cached:
        return cached

    if not messages:
        return None

    conversation_text = "\n".join(f"[{m['author_type']}]: {m['content']}" for m in messages if m.get("content"))

    reason_text = escalation_reason or "low confidence"
    prompt = (
        f"You are a customer support expert. A customer conversation was escalated because: {reason_text}.\n\n"
        f"Conversation:\n{conversation_text}\n\n"
        "Based on this conversation, suggest a helpful reply that the support agent can send to resolve the customer's issue. "
        "Be concise, empathetic, and actionable. Reply with ONLY the suggested message text, nothing else."
    )

    try:
        client = get_llm_client("openai")
        response = await client.generate(
            model="gpt-4o-mini",
            system_prompt="You are a helpful customer support assistant.",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        suggestion = response.strip()
        r.setex(cache_key, CACHE_TTL, suggestion)
        return suggestion
    except Exception as e:
        logger.error(f"Failed to generate suggestion for {conversation_id}: {e}")
        return None
