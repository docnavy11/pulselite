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
    openrouter_base_url: str | None = None,
    actions: list | None = None,
) -> AsyncGenerator[str | RAGResult | dict, None]:
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

    # --- Tool calling step (pre-response action detection) ---
    if actions:
        from app.services.action_tools import build_tool_definitions, action_id_for_tool_name
        from app.services.action_service import get_action
        from app.services.action_executor import execute_action, _get_workspace_slack_webhook
        from app.services.llm import get_llm_client

        tools = build_tool_definitions(actions)
        if tools:
            provider = "openrouter" if openrouter_key else chatbot.llm_provider
            client = get_llm_client(provider, api_key=openrouter_key, base_url=openrouter_base_url)
            tool_result = await client.generate_with_tools(
                messages=messages,
                model=chatbot.llm_model,
                tools=tools,
                temperature=0.0,
                max_tokens=200,
            )

            if tool_result["type"] == "tool_call":
                action_id_str = action_id_for_tool_name(tool_result["tool_name"])
                if action_id_str:
                    import uuid as _uuid
                    action = await get_action(db, _uuid.UUID(action_id_str), chatbot.workspace_id)
                    if action:
                        slack_webhook = await _get_workspace_slack_webhook(db, chatbot.workspace_id)
                        context = {
                            "conversation_id": str(conversation_id) if conversation_id else "",
                            "message": query,
                            "response": "",
                            **tool_result["arguments"],
                        }
                        status, client_payload = await execute_action(action, context, slack_webhook)

                        # Log action event
                        from app.models.actions import ActionEvent
                        event = ActionEvent(
                            id=_uuid.uuid4(),
                            workspace_id=chatbot.workspace_id,
                            chatbot_id=chatbot.id,
                            conversation_id=conversation_id,
                            action_id=action.id,
                            action_type=action.action_type,
                            payload=context,
                            status=status,
                        )
                        db.add(event)
                        await db.flush()

                        if client_payload:
                            yield client_payload  # resolution_service handles dict items as action payloads

                        tool_note = f"Action '{action.name}' triggered successfully."
                        messages.append({"role": "assistant", "content": tool_note})

    async for item in stream_response(messages, chatbot, openrouter_key=openrouter_key, openrouter_base_url=openrouter_base_url):
        yield item
