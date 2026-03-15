import asyncio
import json
import logging
import re
import uuid

from sqlalchemy import select

from app.database import async_session_factory, engine
from app.models.knowledge import Chatbot, Chunk, Document, KnowledgeBase
from app.models.qa import QAPair
from app.services.llm import get_internal_model, get_llm_client
from app.services.rag.prompts import build_system_prompt, build_context_prompt
from app.services.rag.retriever import hybrid_search
from app.services.rag.reranker import rerank
from app.services.realtime import emit_to_workspace, emit_task_event
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

QUESTION_GENERATION_PROMPT = """You are given content from a knowledge base for a customer-facing chatbot.
Generate exactly {count} realistic questions that a real user would ask this chatbot.

Rules:
- Questions should be diverse and cover different topics from the content
- Questions should sound natural, like a real customer would phrase them
- Mix simple factual questions with more complex "how do I..." questions
- Do NOT include answers, only questions
{language_instruction}- Return ONLY a JSON array of strings, no explanation

Knowledge base content:
{content}"""

QA_CONFIDENCE_SUFFIX = """

After your answer, on the VERY LAST LINE, add a confidence rating in this exact format:
CONFIDENCE: <number 0-100>

- 90-100: answer is clearly supported by the context
- 60-89: partially supported, some information may be missing
- 30-59: weakly supported, significant gaps
- 0-29: context does not contain relevant information"""

SUGGEST_ANSWER_PROMPT = """You are an expert at writing clear, helpful customer support answers.

Given this knowledge base content and question, write the best possible answer.
The chatbot previously generated this response which was not satisfactory:

Previous response: {previous_answer}

Knowledge base content:
{content}

Question: {question}

Write a clear, accurate, helpful answer based on the knowledge base content. If the content doesn't contain enough information, say so honestly."""


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation for dedup comparison."""
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def generate_qa(self, chatbot_id: str, workspace_id: str, count: int) -> dict:
    try:
        return asyncio.run(_generate(uuid.UUID(chatbot_id), uuid.UUID(workspace_id), count, self.request.id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _generate(chatbot_id: uuid.UUID, workspace_id: uuid.UUID, count: int, task_id: str) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        await emit_task_event(workspace_id, "started", "generate_qa", task_id,
                              detail=f"Generating {count} Q&A pairs")

        # Load chatbot
        result = await session.execute(select(Chatbot).where(Chatbot.id == chatbot_id))
        chatbot = result.scalar_one_or_none()
        if not chatbot:
            await emit_task_event(workspace_id, "completed", "generate_qa", task_id,
                                  error="Chatbot not found")
            return {"status": "error", "reason": "chatbot not found"}

        # Get KB IDs
        kb_result = await session.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.chatbot_id == chatbot_id)
        )
        kb_ids = [row[0] for row in kb_result.all()]
        if not kb_ids:
            return {"status": "error", "reason": "no knowledge base"}

        # Get indexed document IDs
        doc_result = await session.execute(
            select(Document.id).where(
                Document.knowledge_base_id.in_(kb_ids),
                Document.status == "indexed",
            )
        )
        doc_ids = [row[0] for row in doc_result.all()]
        if not doc_ids:
            return {"status": "error", "reason": "no indexed documents"}

        # Round-robin sample: up to ~50 chunks spread across docs
        chunks_per_doc = max(1, 50 // len(doc_ids))
        all_chunks = []
        for doc_id in doc_ids:
            chunk_result = await session.execute(
                select(Chunk.content)
                .where(Chunk.document_id == doc_id)
                .order_by(Chunk.chunk_index)
                .limit(chunks_per_doc)
            )
            all_chunks.extend([row[0] for row in chunk_result.all()])

        if len(all_chunks) < 5:
            logger.warning("KB has only %d chunks, may generate poor questions", len(all_chunks))

        # Build content summary (truncate to ~8000 chars)
        content = "\n\n---\n\n".join(all_chunks)[:8000]

        # Generate questions via LLM, respecting chatbot language
        language = chatbot.language or "en"
        lang_names = {"en": "English", "nl": "Dutch", "fr": "French", "de": "German", "es": "Spanish", "pt": "Portuguese", "it": "Italian"}
        lang_name = lang_names.get(language, language)
        language_instruction = (
            f"- IMPORTANT: Write ALL questions in {lang_name}\n"
            if language != "en" else ""
        )

        internal_model = await get_internal_model(session, chatbot.workspace_id)
        client = get_llm_client("openrouter")
        response = await client.generate(
            messages=[
                {"role": "system", "content": "You generate realistic customer questions. Always respond with a valid JSON array of strings."},
                {"role": "user", "content": QUESTION_GENERATION_PROMPT.format(count=count, content=content, language_instruction=language_instruction)},
            ],
            model=internal_model,
            temperature=0.8,
            max_tokens=2000,
        )
        text = (response or "[]").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            questions = json.loads(text)
        except json.JSONDecodeError:
            logger.error("LLM returned non-JSON for question generation: %s", text[:200])
            return {"status": "error", "reason": "LLM returned invalid JSON"}

        if not isinstance(questions, list):
            return {"status": "error", "reason": "LLM did not return a list"}

        # Deduplicate against existing pairs (normalized exact match)
        existing_result = await session.execute(
            select(QAPair.question).where(QAPair.chatbot_id == chatbot_id)
        )
        existing_questions = {_normalize(row[0]) for row in existing_result.all()}

        new_questions = []
        for q in questions:
            if isinstance(q, str) and _normalize(q) not in existing_questions:
                new_questions.append(q)
                existing_questions.add(_normalize(q))

        # Insert QA pairs
        pair_ids = []
        for q in new_questions:
            pair = QAPair(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                chatbot_id=chatbot_id,
                question=q,
                status="pending",
            )
            session.add(pair)
            pair_ids.append(str(pair.id))

        await session.commit()

        # Emit event (tests are triggered separately by the user)
        await emit_to_workspace(
            str(workspace_id),
            "qa:questions_generated",
            {"chatbot_id": str(chatbot_id), "count": len(pair_ids)},
        )

        await emit_task_event(workspace_id, "completed", "generate_qa", task_id,
                              detail=f"Generated {len(pair_ids)} Q&A pairs")
        return {"status": "success", "generated": len(pair_ids)}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def test_qa_question(self, qa_pair_id: str) -> dict:
    try:
        return asyncio.run(_test_question(uuid.UUID(qa_pair_id), self.request.id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _test_question(qa_pair_id: uuid.UUID, task_id: str) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        result = await session.execute(select(QAPair).where(QAPair.id == qa_pair_id))
        pair = result.scalar_one_or_none()
        if not pair:
            return {"status": "error", "reason": "pair not found"}

        pair.status = "testing"
        await session.commit()

        await emit_task_event(pair.workspace_id, "started", "test_qa_question", task_id,
                              detail=pair.question[:80])

        # Load chatbot
        chatbot_result = await session.execute(select(Chatbot).where(Chatbot.id == pair.chatbot_id))
        chatbot = chatbot_result.scalar_one_or_none()
        if not chatbot:
            pair.status = "failed"
            pair.error_message = "Chatbot not found"
            await session.commit()
            return {"status": "error", "reason": "chatbot not found"}

        try:
            # Retrieve and rerank chunks (same as RAG pipeline)
            kb_result = await session.execute(
                select(KnowledgeBase).where(KnowledgeBase.chatbot_id == chatbot.id).limit(1)
            )
            kb = kb_result.scalar_one_or_none()
            if not kb:
                pair.status = "failed"
                pair.error_message = "No knowledge base"
                await session.commit()
                return {"status": "error", "reason": "no knowledge base"}

            candidates = await hybrid_search(session, chatbot.workspace_id, kb.id, pair.question, top_k=20)

            if chatbot.use_reranking and candidates:
                scored_chunks = rerank(pair.question, candidates, top_k=chatbot.retrieval_top_k)
            else:
                scored_chunks = [(c, 0.5) for c in candidates[:chatbot.retrieval_top_k]]

            # Build prompt with context
            system_prompt = build_system_prompt(chatbot)
            context_prompt = build_context_prompt(scored_chunks)

            # Single LLM call — answer naturally, then append CONFIDENCE: N on the last line
            messages = [
                {"role": "system", "content": system_prompt + QA_CONFIDENCE_SUFFIX},
                {"role": "user", "content": f"{context_prompt}\n\nQuestion: {pair.question}"},
            ]

            internal_model = await get_internal_model(session, chatbot.workspace_id)
            client = get_llm_client("openrouter")
            response = await client.generate(
                messages=messages,
                model=internal_model,
                temperature=0.1,
                max_tokens=2000,
            )

            # Extract confidence from last line, rest is the answer
            text = (response or "").strip()
            raw_confidence = 50
            confidence_match = re.search(r'CONFIDENCE:\s*(\d+)\s*$', text)
            if confidence_match:
                raw_confidence = int(confidence_match.group(1))
                pair.answer = text[:confidence_match.start()].strip()
            else:
                pair.answer = text

            pair.confidence_score = max(0.0, min(1.0, float(raw_confidence) / 100.0))
            pair.escalated = pair.confidence_score < chatbot.confidence_threshold

            # Source metadata
            doc_ids = list({chunk.document_id for chunk, _ in scored_chunks})
            if doc_ids:
                docs_result = await session.execute(
                    select(Document.id, Document.title, Document.source_url).where(Document.id.in_(doc_ids))
                )
                docs_by_id = {r[0]: {"title": r[1], "source_url": r[2]} for r in docs_result.all()}
                seen: set[uuid.UUID] = set()
                sources: list[dict] = []
                for chunk, _ in scored_chunks:
                    if chunk.document_id not in seen:
                        doc_info = docs_by_id.get(chunk.document_id)
                        if doc_info and doc_info.get("source_url"):
                            sources.append({"title": doc_info["title"], "url": doc_info["source_url"]})
                            seen.add(chunk.document_id)
                pair.sources = [{"chunk_id": str(c.id)} for c, _ in scored_chunks] + sources

            pair.status = "completed"

        except Exception as exc:
            logger.exception("Failed to test QA pair %s", qa_pair_id)
            pair.status = "failed"
            pair.error_message = str(exc)[:500]

        await session.commit()

        is_error = pair.status == "failed"
        await emit_task_event(pair.workspace_id, "completed", "test_qa_question", task_id,
                              detail=f"Score: {pair.confidence_score}" if not is_error else None,
                              error=pair.error_message if is_error else None)

        # Emit update
        await emit_to_workspace(
            str(pair.workspace_id),
            "qa:pair_updated",
            {
                "qa_pair_id": str(pair.id),
                "status": pair.status,
                "confidence_score": pair.confidence_score,
                "escalated": pair.escalated,
                "answer": pair.answer,
                "suggested_answer": pair.suggested_answer,
            },
        )

        return {"status": pair.status, "qa_pair_id": str(qa_pair_id)}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def suggest_qa_answer(self, qa_pair_id: str, workspace_id: str) -> dict:
    try:
        return asyncio.run(_suggest(uuid.UUID(qa_pair_id), uuid.UUID(workspace_id), self.request.id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _suggest(qa_pair_id: uuid.UUID, workspace_id: uuid.UUID, task_id: str) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        result = await session.execute(select(QAPair).where(QAPair.id == qa_pair_id))
        pair = result.scalar_one_or_none()
        if not pair:
            await emit_task_event(workspace_id, "completed", "suggest_qa_answer", task_id,
                                  error="Pair not found")
            return {"status": "error", "reason": "pair not found"}

        await emit_task_event(workspace_id, "started", "suggest_qa_answer", task_id,
                              detail=pair.question[:80])

        # Load relevant chunks for context
        kb_result = await session.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.chatbot_id == pair.chatbot_id)
        )
        kb_ids = [row[0] for row in kb_result.all()]

        chunk_result = await session.execute(
            select(Chunk.content)
            .where(Chunk.knowledge_base_id.in_(kb_ids))
            .limit(30)
        )
        content = "\n\n---\n\n".join([row[0] for row in chunk_result.all()])[:6000]

        internal_model = await get_internal_model(session, workspace_id)
        client = get_llm_client("openrouter")
        response = await client.generate(
            messages=[
                {"role": "system", "content": "You write clear, helpful customer support answers."},
                {
                    "role": "user",
                    "content": SUGGEST_ANSWER_PROMPT.format(
                        content=content,
                        question=pair.question,
                        previous_answer=pair.answer or "(no previous answer)",
                    ),
                },
            ],
            model=internal_model,
            temperature=0.3,
            max_tokens=1000,
        )

        pair.suggested_answer = (response or "").strip()
        await session.commit()

        await emit_task_event(workspace_id, "completed", "suggest_qa_answer", task_id,
                              detail="Suggestion ready")

        await emit_to_workspace(
            str(workspace_id),
            "qa:pair_updated",
            {
                "qa_pair_id": str(pair.id),
                "status": pair.status,
                "confidence_score": pair.confidence_score,
                "escalated": pair.escalated,
                "answer": pair.answer,
                "suggested_answer": pair.suggested_answer,
            },
        )

        return {"status": "success", "qa_pair_id": str(qa_pair_id)}
