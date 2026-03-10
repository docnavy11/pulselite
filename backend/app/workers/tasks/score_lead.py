import asyncio
import re
import uuid

import redis.asyncio as aioredis
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models.contacts import Contact
from app.models.conversations import Conversation
from app.services.integrations.hubspot import push_lead_to_hubspot
from app.workers.celery_app import celery_app

SCORING_RULES = [
    (r"\b(pricing|cost|how much|plans?|enterprise|subscription)\b", 15, "pricing"),
    (r"\b(intercom|zendesk|chatbase|drift|freshdesk|helpscout)\b", 10, "competitor"),
    (r"\b(asap|urgent|deadline|immediately|right away)\b", 10, "urgency"),
    (r"\b(demo|trial|free trial|test|pilot|poc)\b", 20, "demo_request"),
    (r"\b(my team|our company|we need|our organization)\b", 10, "team_signal"),
    (r"\b(just browsing|homework|student|school project)\b", -15, "negative"),
]

COMPILED_RULES = [(re.compile(pattern, re.IGNORECASE), score, label) for pattern, score, label in SCORING_RULES]


def score_message_sync(message: str) -> tuple[int, list[str]]:
    total = 0
    signals = []
    for pattern, score, label in COMPILED_RULES:
        if pattern.search(message):
            total += score
            signals.append(label)
    return total, signals


@celery_app.task
def score_lead_message(conversation_id: str, message: str) -> dict:
    delta, signals = score_message_sync(message)
    if delta == 0:
        return {"delta": 0, "signals": []}

    asyncio.run(_update_redis_score(conversation_id, delta))
    return {"delta": delta, "signals": signals}


@celery_app.task
def flush_lead_score(conversation_id: str, workspace_id: str) -> dict:
    return asyncio.run(_flush(uuid.UUID(conversation_id), uuid.UUID(workspace_id)))


async def _update_redis_score(conversation_id: str, delta: int) -> None:
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await r.incrby(f"pulse:lead:{conversation_id}", delta)
    await r.close()


async def _flush(conversation_id: uuid.UUID, workspace_id: uuid.UUID) -> dict:
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    key = f"pulse:lead:{conversation_id}"
    score_str = await r.get(key)
    await r.delete(key)
    await r.close()

    if score_str is None:
        return {"status": "no_score"}

    score = max(0, min(100, int(score_str)))
    tier = "hot" if score > 80 else "warm" if score >= 50 else "cold"

    async with async_session_factory() as session:
        try:
            result = await session.execute(select(Conversation.contact_id).where(Conversation.id == conversation_id))
            row = result.one_or_none()
            contact_id = row[0] if row else None

            if contact_id is None:
                return {"status": "no_contact"}

            result = await session.execute(select(Contact).where(Contact.id == contact_id))
            contact = result.scalar_one_or_none()
            if contact:
                contact.lead_score = score
                contact.lead_tier = tier

            contact_email = contact.email if contact else None
            contact_name = contact.name if contact else None
            should_push_hubspot = tier == "hot" and contact_email is not None

            await session.commit()

            if should_push_hubspot:
                await push_lead_to_hubspot(
                    session,
                    workspace_id,
                    email=contact_email,
                    name=contact_name,
                    properties={"lead_source": "Pulse", "hs_lead_status": "NEW", "pulse_lead_score": str(score)},
                )

            return {"status": "flushed", "score": score, "tier": tier}
        except Exception:
            await session.rollback()
            raise
