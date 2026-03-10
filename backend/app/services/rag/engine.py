import logging
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Chatbot, Document, KnowledgeBase
from app.services.rag.confidence import compute_confidence, should_escalate
from app.services.rag.generator import stream_response
from app.services.rag.memory import get_conversation_history
from app.services.rag.prompts import build_context_prompt, build_system_prompt
from app.services.rag.reranker import rerank
from app.services.rag.retriever import hybrid_search

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    confidence_score: float
    confidence_avg: float
    escalated: bool
    retrieved_chunk_ids: list[uuid.UUID]
    query: str
    sources: list[dict] = field(default_factory=list)


async def process_query(
    db: AsyncSession,
    query: str,
    chatbot: Chatbot,
    conversation_id: uuid.UUID | None = None,
    openrouter_key: str | None = None,
) -> AsyncGenerator[str | RAGResult, None]:
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.chatbot_id == chatbot.id).limit(1))
    kb = result.scalar_one_or_none()

    if kb is None:
        yield RAGResult(
            confidence_score=0.0,
            confidence_avg=0.0,
            escalated=True,
            retrieved_chunk_ids=[],
            query=query,
        )
        yield "I don't have a knowledge base configured yet. Please contact support."
        return

    candidates = await hybrid_search(db, chatbot.workspace_id, kb.id, query, top_k=20)

    if chatbot.use_reranking and candidates:
        scored_chunks = rerank(query, candidates, top_k=chatbot.retrieval_top_k)
    else:
        scored_chunks = [(c, 0.5) for c in candidates[: chatbot.retrieval_top_k]]

    confidence_score, confidence_avg = compute_confidence(scored_chunks)
    escalated = should_escalate(confidence_score, chatbot.confidence_threshold)

    retrieved_chunk_ids = [chunk.id for chunk, _ in scored_chunks]

    # Load source document metadata for citations
    doc_ids = list({chunk.document_id for chunk, _ in scored_chunks})
    docs_result = await db.execute(
        select(Document.id, Document.title, Document.source_url).where(Document.id.in_(doc_ids))
    )
    docs_by_id = {row[0]: {"title": row[1], "source_url": row[2]} for row in docs_result.all()}

    seen_docs: set[uuid.UUID] = set()
    sources: list[dict] = []
    for chunk, _ in scored_chunks:
        if chunk.document_id not in seen_docs:
            doc_info = docs_by_id.get(chunk.document_id, {})
            source_url = doc_info.get("source_url")
            if source_url:
                sources.append(
                    {
                        "index": len(sources) + 1,
                        "title": doc_info.get("title") or f"Source {len(sources) + 1}",
                        "url": source_url,
                    }
                )
                seen_docs.add(chunk.document_id)

    rag_result = RAGResult(
        confidence_score=confidence_score,
        confidence_avg=confidence_avg,
        escalated=escalated,
        retrieved_chunk_ids=retrieved_chunk_ids,
        query=query,
        sources=sources,
    )
    yield rag_result

    system_prompt = build_system_prompt(chatbot)
    context_prompt = build_context_prompt(scored_chunks)

    messages = [{"role": "system", "content": system_prompt}]

    if conversation_id:
        history = await get_conversation_history(db, conversation_id)
        messages.extend(history)

    messages.append({"role": "user", "content": f"{context_prompt}\n\nUser question: {query}"})

    async for token in stream_response(messages, chatbot, openrouter_key=openrouter_key):
        yield token
