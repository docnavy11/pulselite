# backend/app/services/autoconfig_service.py
import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Chatbot, Chunk, Document
from app.services.autoconfig import generate
from app.services.fetcher import fetch

logger = logging.getLogger(__name__)

_LANG_RE = re.compile(r'<html[^>]+lang=["\']([a-zA-Z]{2,3})(?:[_-][a-zA-Z]+)?["\']', re.IGNORECASE)

_MAX_CHUNKS = 20


async def run(
    db: AsyncSession,
    chatbot_id: uuid.UUID,
    kb_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> Chatbot:
    # 1. Verify chatbot belongs to workspace
    r = await db.execute(
        select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace_id)
    )
    chatbot = r.scalar_one_or_none()
    if chatbot is None:
        raise ValueError("Chatbot not found")

    # 2. Fetch chunks ordered by chunk_index (deterministic)
    chunks_r = await db.execute(
        select(Chunk)
        .where(Chunk.knowledge_base_id == kb_id, Chunk.workspace_id == workspace_id)
        .order_by(Chunk.chunk_index.asc())
        .limit(_MAX_CHUNKS)
    )
    chunks = list(chunks_r.scalars().all())
    if not chunks:
        raise ValueError("Knowledge base has no indexed content yet")

    chunk_texts = [c.content for c in chunks]

    # 3. Get homepage URL from first Document in KB with source_url
    doc_r = await db.execute(
        select(Document)
        .where(
            Document.knowledge_base_id == kb_id,
            Document.workspace_id == workspace_id,
            Document.source_url.is_not(None),
        )
        .order_by(Document.created_at.asc())
        .limit(1)
    )
    first_doc = doc_r.scalar_one_or_none()
    homepage_html = ""
    if first_doc and first_doc.source_url:
        try:
            fetch_result = await fetch(first_doc.source_url)
            homepage_html = fetch_result.html
        except Exception as exc:
            logger.warning("Failed to fetch homepage for autoconfig: %s", exc)

    # 4. Detect language from homepage HTML lang attribute
    detected_lang: str | None = None
    if homepage_html:
        m = _LANG_RE.search(homepage_html)
        if m:
            detected_lang = m.group(1).lower()

    # 5. Generate config (pass detected language so all text is in the right language)
    config = await generate(chunk_texts, homepage_html, language=detected_lang)

    # 6. Update chatbot fields
    chatbot.name = config.name
    chatbot.welcome_message = config.welcome_message
    chatbot.system_prompt = config.system_prompt
    chatbot.suggested_questions = config.suggested_questions
    chatbot.fallback_message = config.fallback_message
    chatbot.tone = config.tone
    if config.brand_color is not None:
        chatbot.brand_color = config.brand_color
    if detected_lang:
        chatbot.language = detected_lang

    await db.commit()
    await db.refresh(chatbot)
    return chatbot
