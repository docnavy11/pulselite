"""RAG pipeline — consolidates services/rag/ directory (7 files → 1)."""
import logging
import math
import json
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversations import Message
from app.models.knowledge import Chatbot, Chunk, Document, KnowledgeBase

logger = logging.getLogger(__name__)

# --- Retriever ---

DENSE_CANDIDATES = 20
SPARSE_CANDIDATES = 20
RRF_K = 60


async def dense_search(db, workspace_id, knowledge_base_id, query_embedding, limit=DENSE_CANDIDATES):
    distance = Chunk.embedding.cosine_distance(query_embedding)
    result = await db.execute(
        select(Chunk, distance.label("distance"))
        .where(Chunk.workspace_id == workspace_id, Chunk.knowledge_base_id == knowledge_base_id, Chunk.embedding.isnot(None))
        .order_by(distance).limit(limit)
    )
    return [(row[0], 1.0 - row[1]) for row in result.all()]


async def sparse_search(db, workspace_id, knowledge_base_id, query_text, limit=SPARSE_CANDIDATES):
    ts_query = func.plainto_tsquery("english", query_text)
    rank = func.ts_rank_cd(Chunk.search_vector, ts_query)
    result = await db.execute(
        select(Chunk, rank.label("rank"))
        .where(Chunk.workspace_id == workspace_id, Chunk.knowledge_base_id == knowledge_base_id, Chunk.search_vector.op("@@")(ts_query))
        .order_by(rank.desc()).limit(limit)
    )
    return list(result.all())


async def hybrid_search(db, workspace_id, knowledge_base_id, query_text, top_k=10):
    query_embedding = await _embed_query(query_text)
    dense_results = await dense_search(db, workspace_id, knowledge_base_id, query_embedding) if query_embedding else []
    sparse_results = await sparse_search(db, workspace_id, knowledge_base_id, query_text)
    return _reciprocal_rank_fusion(dense_results, sparse_results, top_k)


def _reciprocal_rank_fusion(dense_results, sparse_results, top_k):
    scores = {}
    chunk_map = {}
    for rank, (chunk, _) in enumerate(dense_results):
        chunk_map[chunk.id] = chunk
        scores[chunk.id] = scores.get(chunk.id, 0) + 1.0 / (RRF_K + rank + 1)
    for rank, (chunk, _) in enumerate(sparse_results):
        chunk_map[chunk.id] = chunk
        scores[chunk.id] = scores.get(chunk.id, 0) + 1.0 / (RRF_K + rank + 1)
    sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:top_k]
    return [chunk_map[cid] for cid in sorted_ids]


async def _embed_query(query):
    from app.services.ingestion.embedder import _get_model
    model = _get_model()
    if model is None:
        return None
    result = list(model.embed([query]))
    return result[0].tolist()


# --- Reranker ---

RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _get_reranker():
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        logger.warning("sentence-transformers not installed — reranking disabled")
        return None
    logger.info("Loading reranker model: %s", RERANKER_MODEL)
    return CrossEncoder(RERANKER_MODEL)


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def rerank(query, chunks, top_k=None):
    if not chunks:
        return []
    model = _get_reranker()
    if model is None:
        scored = [(chunk, 0.5) for chunk in chunks]
        return scored[:top_k] if top_k else scored
    pairs = [(query, chunk.content) for chunk in chunks]
    scores = model.predict(pairs)
    scored = list(zip(chunks, [_sigmoid(float(s)) for s in scores]))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k] if top_k else scored


# --- Confidence ---

def compute_confidence(scored_chunks):
    if not scored_chunks:
        return 0.0, 0.0
    scores = [score for _, score in scored_chunks]
    return max(scores), sum(scores) / len(scores)


def should_escalate(confidence_score, threshold):
    return confidence_score < threshold


# --- Memory ---

ROLE_MAP = {"contact": "user", "agent": "assistant", "bot": "assistant", "system": "system"}


async def get_conversation_history(db, conversation_id, limit=10):
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id, Message.message_type.in_(["incoming", "outgoing"]))
        .order_by(Message.created_at.desc()).limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    return [{"role": ROLE_MAP.get(msg.author_type, "user"), "content": msg.content} for msg in messages if msg.content]


# --- Prompts ---

CITATION_INSTRUCTION = """When answering, cite your sources using numbered references like [1], [2], etc.
Only use information from the provided context. If the context doesn't contain enough information to answer the question confidently, say so clearly rather than guessing."""

PERSONA_TEMPLATE = """You are {display_name}, an AI assistant for {chatbot_name}.
Your tone is {tone}. {language_instruction}

{system_prompt}

{citation_instruction}"""


def _build_language_instruction(chatbot):
    language = chatbot.language or "English"
    if getattr(chatbot, "auto_detect_language", False):
        return f"Detect the language of the user's message and always respond in that same language. If unsure, default to {language}."
    return f"You respond in {language}."


def build_system_prompt(chatbot):
    return PERSONA_TEMPLATE.format(
        display_name=chatbot.display_name or "Assistant",
        chatbot_name=chatbot.name,
        tone=chatbot.tone or "professional",
        language_instruction=_build_language_instruction(chatbot),
        system_prompt=chatbot.system_prompt or "",
        citation_instruction=CITATION_INSTRUCTION,
    ).strip()


def build_context_prompt(chunks):
    if not chunks:
        return "No relevant context found."
    parts = ["Here is the relevant context:\n"]
    for i, (chunk, score) in enumerate(chunks, 1):
        heading = f" ({chunk.heading_path})" if chunk.heading_path else ""
        parts.append(f"[{i}]{heading}:\n{chunk.content}\n")
    return "\n".join(parts)


# --- Reformulator ---

REFORMULATION_SYSTEM_PROMPT = (
    "You are a search query optimizer. Given a user question, generate 3 alternative phrasings "
    "that might match different content in a knowledge base. Return JSON only: "
    '{"queries": ["...", "...", "..."]}'
)


async def reformulate_queries(query, chatbot, openrouter_key=None, openrouter_base_url=None):
    try:
        from app.services.llm import get_llm_client
        from app.services.encryption import decrypt_api_key
        api_key = openrouter_key
        if api_key is None and chatbot.byoak:
            api_key = decrypt_api_key(chatbot.byoak)
        provider = "openrouter" if openrouter_key else chatbot.llm_provider
        client = get_llm_client(provider, api_key=api_key, base_url=openrouter_base_url)
        response = await client.generate(
            messages=[{"role": "system", "content": REFORMULATION_SYSTEM_PROMPT}, {"role": "user", "content": query}],
            model=chatbot.llm_model, temperature=0.7, max_tokens=200,
        )
        data = json.loads(response)
        queries = data.get("queries", [])
        return [q for q in queries if isinstance(q, str) and q.strip()] if queries else []
    except Exception:
        logger.warning("Query reformulation failed for: %s", query[:80], exc_info=True)
        return []


# --- Generator ---

async def stream_response(messages, chatbot, openrouter_key=None, openrouter_base_url=None):
    from app.services.llm import get_llm_client
    from app.services.encryption import decrypt_api_key
    api_key = openrouter_key
    if api_key is None and chatbot.byoak:
        try:
            api_key = decrypt_api_key(chatbot.byoak)
        except Exception:
            logger.warning("Failed to decrypt BYOK key for chatbot %s", chatbot.id)
    provider = "openrouter" if openrouter_key else chatbot.llm_provider
    client = get_llm_client(provider, api_key=api_key, base_url=openrouter_base_url)
    async for item in client.stream_generate(messages=messages, model=chatbot.llm_model, temperature=chatbot.temperature, max_tokens=chatbot.max_tokens):
        yield item


# --- RAG Engine (process_query) ---

@dataclass
class RAGResult:
    confidence_score: float
    confidence_avg: float
    escalated: bool
    retrieved_chunk_ids: list[uuid.UUID]
    query: str
    sources: list[dict] = field(default_factory=list)
    retried: bool = False
    original_confidence_low: bool = False


async def process_query(
    db: AsyncSession, query: str, chatbot: Chatbot, conversation_id: uuid.UUID | None = None,
    openrouter_key=None, openrouter_base_url=None, actions=None,
) -> AsyncGenerator[str | RAGResult | dict, None]:
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.chatbot_id == chatbot.id).limit(1))
    kb = result.scalar_one_or_none()
    if kb is None:
        yield RAGResult(confidence_score=0.0, confidence_avg=0.0, escalated=True, retrieved_chunk_ids=[], query=query)
        yield "I don't have a knowledge base configured yet. Please contact support."
        return

    candidates = await hybrid_search(db, chatbot.workspace_id, kb.id, query, top_k=20)

    if chatbot.use_reranking and candidates:
        scored_chunks = rerank(query, candidates, top_k=chatbot.retrieval_top_k)
    else:
        scored_chunks = [(c, 0.5) for c in candidates[:chatbot.retrieval_top_k]]

    confidence_score, confidence_avg = compute_confidence(scored_chunks)
    escalated = should_escalate(confidence_score, chatbot.confidence_threshold)
    original_confidence_low = escalated

    if original_confidence_low:
        retry_queries = await reformulate_queries(query, chatbot, openrouter_key, openrouter_base_url)
        if retry_queries:
            all_chunks = list(candidates)
            seen_ids = {c.id for c in candidates}
            for rq in retry_queries:
                new_candidates = await hybrid_search(db, chatbot.workspace_id, kb.id, rq, top_k=20)
                for c in new_candidates:
                    if c.id not in seen_ids:
                        all_chunks.append(c)
                        seen_ids.add(c.id)
            if all_chunks:
                scored_chunks = rerank(query, all_chunks, top_k=chatbot.retrieval_top_k)
                confidence_score, confidence_avg = compute_confidence(scored_chunks)
                escalated = should_escalate(confidence_score, chatbot.confidence_threshold)

    retrieved_chunk_ids = [chunk.id for chunk, _ in scored_chunks]

    doc_ids = list({chunk.document_id for chunk, _ in scored_chunks})
    docs_result = await db.execute(select(Document.id, Document.title, Document.source_url).where(Document.id.in_(doc_ids)))
    docs_by_id = {row[0]: {"title": row[1], "source_url": row[2]} for row in docs_result.all()}

    seen_docs = set()
    sources = []
    for chunk, _ in scored_chunks:
        if chunk.document_id not in seen_docs:
            doc_info = docs_by_id.get(chunk.document_id, {})
            if doc_info.get("source_url"):
                sources.append({"index": len(sources) + 1, "title": doc_info.get("title") or f"Source {len(sources) + 1}", "url": doc_info["source_url"]})
                seen_docs.add(chunk.document_id)

    rag_result = RAGResult(
        confidence_score=confidence_score, confidence_avg=confidence_avg, escalated=escalated,
        retrieved_chunk_ids=retrieved_chunk_ids, query=query, sources=sources,
        retried=bool(original_confidence_low and not escalated), original_confidence_low=original_confidence_low,
    )
    yield rag_result

    system_prompt_text = build_system_prompt(chatbot)
    context_prompt = build_context_prompt(scored_chunks)
    messages = [{"role": "system", "content": system_prompt_text}]
    if conversation_id:
        history = await get_conversation_history(db, conversation_id)
        messages.extend(history)
    messages.append({"role": "user", "content": f"{context_prompt}\n\nUser question: {query}"})

    # Tool calling for actions with parameters
    if actions:
        from app.services.action_tools import build_tool_definitions, action_id_for_tool_name
        from app.services.action_service import get_action
        from app.services.action_executor import execute_action, _get_workspace_slack_webhook
        from app.services.llm import get_llm_client as _get_client
        tools = build_tool_definitions(actions)
        if tools:
            provider = "openrouter" if openrouter_key else chatbot.llm_provider
            client = _get_client(provider, api_key=openrouter_key, base_url=openrouter_base_url)
            tool_result = await client.generate_with_tools(messages=messages, model=chatbot.llm_model, tools=tools, temperature=0.0, max_tokens=200)
            if tool_result["type"] == "tool_call":
                action_id_str = action_id_for_tool_name(tool_result["tool_name"])
                if action_id_str:
                    action = await get_action(db, uuid.UUID(action_id_str), chatbot.workspace_id)
                    if action:
                        slack_webhook = await _get_workspace_slack_webhook(db, chatbot.workspace_id)
                        context = {"conversation_id": str(conversation_id) if conversation_id else "", "message": query, "response": "", **tool_result["arguments"]}
                        status, client_payload = await execute_action(action, context, slack_webhook)
                        from app.models.actions import ActionEvent
                        event = ActionEvent(id=uuid.uuid4(), workspace_id=chatbot.workspace_id, chatbot_id=chatbot.id, conversation_id=conversation_id, action_id=action.id, action_type=action.action_type, payload=context, status=status)
                        db.add(event)
                        await db.flush()
                        if client_payload:
                            yield client_payload
                        messages.append({"role": "assistant", "content": f"Action '{action.name}' triggered successfully."})

    async for item in stream_response(messages, chatbot, openrouter_key=openrouter_key, openrouter_base_url=openrouter_base_url):
        yield item
