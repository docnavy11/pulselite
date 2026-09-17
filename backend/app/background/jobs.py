"""Background job definitions — replaces workers/tasks/ (16 files → 1).

Each function is a plain async coroutine registered via @register_job.
Jobs receive a payload dict and run in their own database session.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update

from app.background.runner import enqueue, register_job
from app.database import async_session_factory

logger = logging.getLogger(__name__)


# --- Crawl ---


@register_job("crawl_website")
async def crawl_website(payload: dict):
    job_id = uuid.UUID(payload["job_id"])
    async with async_session_factory() as db:
        from app.services.crawl_service import execute_crawl

        try:
            await execute_crawl(db, job_id)
        except Exception as exc:
            from app.models.knowledge import CrawlJob

            result = await db.execute(select(CrawlJob).where(CrawlJob.id == job_id))
            job = result.scalar_one_or_none()
            if job and job.status != "failed":
                job.status = "failed"
                job.error_message = str(exc)[:500]
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
            raise


# --- Ingest ---


@register_job("ingest_document")
async def ingest_document(payload: dict):
    doc_id = uuid.UUID(payload["document_id"])
    async with async_session_factory() as db:
        from app.models.knowledge import Chatbot, Document, KnowledgeBase
        from app.services.ingestion import run_ingestion

        await run_ingestion(db, doc_id)
        await db.commit()

        # Check if all documents in KB are done → trigger autoconfig
        doc_result = await db.execute(select(Document).where(Document.id == doc_id))
        doc = doc_result.scalar_one_or_none()
        if not doc:
            return

        kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == doc.knowledge_base_id))
        kb = kb_result.scalar_one_or_none()
        if not kb or not kb.chatbot_id:
            return

        # Count pending/processing docs in this KB
        pending = await db.execute(
            select(func.count(Document.id)).where(
                Document.knowledge_base_id == kb.id,
                Document.status.in_(["pending", "processing"]),
            )
        )
        if pending.scalar_one() > 0:
            return

        # All done — check if chatbot is in "crawling" state
        chatbot_result = await db.execute(select(Chatbot).where(Chatbot.id == kb.chatbot_id))
        chatbot = chatbot_result.scalar_one_or_none()
        if chatbot and chatbot.setup_status == "crawling":
            # Atomically transition to configuring
            updated = await db.execute(
                update(Chatbot)
                .where(Chatbot.id == chatbot.id, Chatbot.setup_status == "crawling")
                .values(setup_status="configuring")
                .returning(Chatbot.id)
            )
            if updated.fetchone():
                await db.commit()
                from app.background.runner import submit_job

                await submit_job(
                    "run_autoconfig",
                    {
                        "chatbot_id": str(chatbot.id),
                        "kb_id": str(kb.id),
                        "workspace_id": str(chatbot.workspace_id),
                    },
                )


# --- Autoconfig ---


@register_job("run_autoconfig")
async def run_autoconfig(payload: dict):
    chatbot_id = uuid.UUID(payload["chatbot_id"])
    kb_id = uuid.UUID(payload["kb_id"])
    workspace_id = uuid.UUID(payload["workspace_id"])
    async with async_session_factory() as db:
        from app.models.knowledge import Chatbot
        from app.realtime.events import notify_workspace
        from app.services.autoconfig_service import run

        try:
            await run(db, chatbot_id, kb_id, workspace_id)
            result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id))
            chatbot = result.scalar_one_or_none()
            if chatbot:
                chatbot.setup_status = "ready"
                await db.commit()
                await notify_workspace(
                    str(workspace_id),
                    "chatbot:status_changed",
                    {
                        "chatbot_id": str(chatbot_id),
                        "setup_status": "ready",
                    },
                )
        except Exception as exc:
            logger.exception("Autoconfig failed for chatbot %s", chatbot_id)
            result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id))
            chatbot = result.scalar_one_or_none()
            if chatbot:
                chatbot.setup_status = "setup_failed"
                chatbot.setup_error = str(exc)[:500]
                await db.commit()
                await notify_workspace(
                    str(workspace_id),
                    "chatbot:status_changed",
                    {
                        "chatbot_id": str(chatbot_id),
                        "setup_status": "setup_failed",
                        "error": str(exc)[:200],
                    },
                )
            raise


# --- Analyze conversation ---


@register_job("analyze_conversation")
async def analyze_conversation(payload: dict):
    conversation_id = uuid.UUID(payload["conversation_id"])
    workspace_id = uuid.UUID(payload["workspace_id"])
    force = payload.get("force", False)
    async with async_session_factory() as db:
        from app.models.conversations import Conversation, Message
        from app.models.intelligence import ConversationAnalysis
        from app.services.llm import get_internal_client, get_internal_model

        if not force:
            existing = await db.execute(
                select(ConversationAnalysis).where(ConversationAnalysis.conversation_id == conversation_id)
            )
            if existing.scalar_one_or_none():
                return

        conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conv = conv_result.scalar_one_or_none()
        if not conv:
            return

        msgs_result = await db.execute(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
        )
        messages = msgs_result.scalars().all()
        if not messages:
            return

        transcript = "\n".join(f"{m.author_type}: {m.content}" for m in messages if m.content)
        model = await get_internal_model(db, workspace_id)
        client = get_internal_client()

        import json

        prompt = f"""Analyze this conversation and return JSON:
{{
  "sentiment_score": <float -1 to 1>,
  "sentiment_label": "<positive|neutral|negative>",
  "intent_primary": "<string>",
  "topics": ["<topic1>", "<topic2>"],
  "outcome_category": "<resolved|unresolved|escalated|abandoned>",
  "summary": "<2 sentences>"
}}

Conversation:
{transcript}"""

        raw = await client.generate(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            temperature=0.0,
            max_tokens=500,
        )
        try:
            import re

            cleaned = re.sub(r"^```(?:json)?\s*\n?", "", raw.strip())
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)
            data = json.loads(cleaned)
        except Exception:
            logger.warning("Failed to parse analysis JSON for conversation %s", conversation_id)
            return

        analysis = ConversationAnalysis(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            sentiment_score=data.get("sentiment_score"),
            sentiment_label=data.get("sentiment_label"),
            intent_primary=data.get("intent_primary"),
            topics=data.get("topics"),
            outcome_category=data.get("outcome_category"),
            summary=data.get("summary"),
        )
        db.add(analysis)
        await db.commit()


# --- Sentiment trends ---


@register_job("compute_sentiment_trends")
async def compute_sentiment_trends(payload: dict):
    """Compute daily sentiment averages across all workspaces."""
    async with async_session_factory() as db:
        from app.models.intelligence import ConversationAnalysis
        from app.models.organizational import Workspace

        workspaces = await db.execute(select(Workspace.id))
        for (ws_id,) in workspaces.all():
            # Get average sentiment for last 24h
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            result = await db.execute(
                select(func.avg(ConversationAnalysis.sentiment_score)).where(
                    ConversationAnalysis.workspace_id == ws_id,
                    ConversationAnalysis.created_at >= yesterday,
                    ConversationAnalysis.sentiment_score.isnot(None),
                )
            )
            avg = result.scalar_one()
            if avg is not None and avg < -0.3:
                logger.warning("Low sentiment alert for workspace %s: avg=%.2f", ws_id, avg)


# --- Gap clustering ---


@register_job("cluster_gaps")
async def cluster_gaps(payload: dict):
    """Cluster unanswered questions using BERTopic."""
    async with async_session_factory() as db:
        from app.models.intelligence import GapCluster, GapEvent
        from app.models.organizational import Workspace

        workspaces = await db.execute(select(Workspace.id, Workspace.intelligence_config))
        for ws_id, config in workspaces.all():
            if not config.get("gap_clustering", True):
                continue

            events = await db.execute(
                select(GapEvent)
                .where(GapEvent.workspace_id == ws_id, GapEvent.gap_cluster_id.is_(None))
                .order_by(GapEvent.created_at.desc())
                .limit(500)
            )
            gap_events = events.scalars().all()
            if len(gap_events) < 5:
                continue

            queries = [e.query for e in gap_events]
            try:
                from bertopic import BERTopic

                topic_model = BERTopic(min_topic_size=3, nr_topics="auto")
                topics, _ = topic_model.fit_transform(queries)
            except Exception:
                logger.warning("BERTopic clustering failed for workspace %s", ws_id, exc_info=True)
                continue

            topic_info = topic_model.get_topic_info()
            for _, row in topic_info.iterrows():
                topic_id = row["Topic"]
                if topic_id == -1:
                    continue
                indices = [i for i, t in enumerate(topics) if t == topic_id]
                if not indices:
                    continue

                cluster = GapCluster(
                    id=uuid.uuid4(),
                    workspace_id=ws_id,
                    topic_label=row.get("Name", f"Topic {topic_id}")[:200],
                    gap_count=len(indices),
                    representative_query=queries[indices[0]] if indices else None,
                )
                db.add(cluster)
                await db.flush()

                for idx in indices:
                    gap_events[idx].gap_cluster_id = cluster.id

            await db.commit()


# --- Q&A generation ---


@register_job("generate_qa")
async def generate_qa(payload: dict):
    chatbot_id = uuid.UUID(payload["chatbot_id"])
    workspace_id = uuid.UUID(payload["workspace_id"])
    async with async_session_factory() as db:
        import json
        import random

        from app.models.knowledge import Chatbot, Chunk, KnowledgeBase
        from app.models.qa import QAPair
        from app.services.llm import get_internal_client, get_internal_model

        chatbot_result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id))
        chatbot = chatbot_result.scalar_one_or_none()
        if not chatbot:
            return

        kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.chatbot_id == chatbot_id).limit(1))
        kb = kb_result.scalar_one_or_none()
        if not kb:
            return

        chunks_result = await db.execute(
            select(Chunk).where(Chunk.knowledge_base_id == kb.id).order_by(Chunk.chunk_index.asc()).limit(50)
        )
        chunks = chunks_result.scalars().all()
        if not chunks:
            return

        sampled = random.sample(chunks, min(20, len(chunks)))
        content = "\n\n---\n\n".join(c.content for c in sampled)

        model = await get_internal_model(db, workspace_id)
        client = get_internal_client()

        prompt = f"""Based on this content, generate 10 realistic Q&A pairs that a customer might ask.
Return JSON array: [{{"question": "...", "answer": "..."}}]

Content:
{content}"""

        raw = await client.generate(
            messages=[{"role": "user", "content": prompt}], model=model, temperature=0.5, max_tokens=2000
        )
        try:
            import re

            cleaned = re.sub(r"^```(?:json)?\s*\n?", "", raw.strip())
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)
            pairs = json.loads(cleaned)
        except Exception:
            logger.warning("Failed to parse QA generation JSON")
            return

        existing = await db.execute(select(QAPair.question).where(QAPair.chatbot_id == chatbot_id))
        existing_questions = {q.lower().strip() for (q,) in existing.all()}

        for pair in pairs:
            q = pair.get("question", "").strip()
            a = pair.get("answer", "").strip()
            if not q or q.lower().strip() in existing_questions:
                continue
            qa = QAPair(workspace_id=workspace_id, chatbot_id=chatbot_id, question=q, answer=a, status="pending")
            db.add(qa)
            existing_questions.add(q.lower().strip())

        await db.commit()
        from app.realtime.events import notify_workspace

        await notify_workspace(str(workspace_id), "qa:questions_generated", {"chatbot_id": str(chatbot_id)})


# --- Document sync ---


@register_job("sync_documents")
async def sync_documents(payload: dict):
    async with async_session_factory() as db:
        from app.models.knowledge import Document

        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(Document)
            .where(
                Document.next_sync_at <= now,
                Document.sync_frequency != "manual",
                Document.status == "indexed",
            )
            .limit(100)
        )
        docs = result.scalars().all()
        for doc in docs:
            enqueue(_reingest(doc.id), name=f"sync:{doc.id}")


async def _reingest(doc_id: uuid.UUID):
    async with async_session_factory() as db:
        from app.services.ingestion import run_ingestion

        await run_ingestion(db, doc_id)
        await db.commit()


# --- Close stale conversations ---


@register_job("close_stale_conversations")
async def close_stale_conversations(payload: dict):
    async with async_session_factory() as db:
        from app.models.conversations import Conversation

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        result = await db.execute(
            update(Conversation)
            .where(Conversation.status == "open", Conversation.updated_at < cutoff)
            .values(status="closed", resolved_at=datetime.now(timezone.utc))
            .returning(Conversation.id, Conversation.workspace_id)
        )
        closed = result.all()
        await db.commit()

        # Trigger analysis for closed conversations
        from app.background.runner import submit_job

        for conv_id, ws_id in closed:
            await submit_job("analyze_conversation", {"conversation_id": str(conv_id), "workspace_id": str(ws_id)})


# --- Purge old data ---


@register_job("purge_old_data")
async def purge_old_data(payload: dict):
    async with async_session_factory() as db:
        from app.models.conversations import Conversation
        from app.models.organizational import Workspace

        workspaces = await db.execute(
            select(Workspace.id, Workspace.data_retention_days).where(Workspace.data_retention_days.isnot(None))
        )
        for ws_id, retention_days in workspaces.all():
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            await db.execute(
                delete(Conversation).where(Conversation.workspace_id == ws_id, Conversation.created_at < cutoff)
            )
        await db.commit()


# --- GDPR export ---


@register_job("gdpr_export")
async def gdpr_export(payload: dict):
    workspace_id = uuid.UUID(payload["workspace_id"])
    export_id = payload.get("export_id", str(uuid.uuid4()))
    async with async_session_factory() as db:
        import json
        import os

        from app.models.contacts import Contact
        from app.models.conversations import Conversation

        contacts = await db.execute(select(Contact).where(Contact.workspace_id == workspace_id))
        conversations = await db.execute(select(Conversation).where(Conversation.workspace_id == workspace_id))

        export_data = {
            "workspace_id": str(workspace_id),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "contacts": [{"id": str(c.id), "email": c.email, "name": c.name} for c in contacts.scalars().all()],
            "conversations": [
                {"id": str(c.id), "status": c.status, "created_at": c.created_at.isoformat()}
                for c in conversations.scalars().all()
            ],
        }

        export_dir = "/app/data/exports"
        os.makedirs(export_dir, mode=0o700, exist_ok=True)
        path = os.path.join(export_dir, f"{export_id}.json")
        with open(path, "w") as f:
            json.dump(export_data, f, indent=2)

        logger.info("GDPR export %s completed for workspace %s", export_id, workspace_id)


# --- Q&A testing ---


@register_job("test_qa_question")
async def test_qa_question(payload: dict):
    """Run a single QA pair through the RAG pipeline and score it."""
    qa_id = uuid.UUID(payload["qa_id"])
    async with async_session_factory() as db:
        from app.models.knowledge import Chatbot, Document, KnowledgeBase
        from app.models.organizational import Workspace
        from app.models.qa import QAPair
        from app.services.encryption import decrypt_api_key
        from app.services.llm import get_internal_client, get_internal_model, get_llm_client
        from app.services.rag import (
            build_context_prompt,
            build_system_prompt,
            compute_confidence,
            hybrid_search,
            rerank,
            should_escalate,
        )

        pair = (await db.execute(select(QAPair).where(QAPair.id == qa_id))).scalar_one_or_none()
        if not pair:
            return

        chatbot = (await db.execute(select(Chatbot).where(Chatbot.id == pair.chatbot_id))).scalar_one_or_none()
        if not chatbot:
            pair.status = "failed"
            pair.error_message = "Chatbot not found"
            await db.commit()
            return

        kb = (
            await db.execute(select(KnowledgeBase).where(KnowledgeBase.chatbot_id == chatbot.id).limit(1))
        ).scalar_one_or_none()
        if not kb:
            pair.status = "failed"
            pair.error_message = "No knowledge base configured"
            await db.commit()
            return

        ws = (await db.execute(select(Workspace).where(Workspace.id == pair.workspace_id))).scalar_one_or_none()
        openrouter_key = None
        openrouter_base_url = None
        if ws:
            openrouter_base_url = ws.openrouter_base_url
            if ws.openrouter_api_key:
                try:
                    openrouter_key = decrypt_api_key(ws.openrouter_api_key)
                except Exception:
                    pass

        try:
            candidates = await hybrid_search(db, chatbot.workspace_id, kb.id, pair.question, top_k=20)
            if chatbot.use_reranking and candidates:
                scored_chunks = rerank(pair.question, candidates, top_k=chatbot.retrieval_top_k)
            else:
                scored_chunks = [(c, 0.5) for c in candidates[: chatbot.retrieval_top_k]]

            confidence_score, _ = compute_confidence(scored_chunks)
            escalated = should_escalate(confidence_score, chatbot.confidence_threshold)

            doc_ids = list({chunk.document_id for chunk, _ in scored_chunks})
            docs_result = await db.execute(
                select(Document.id, Document.title, Document.source_url).where(Document.id.in_(doc_ids))
            )
            docs_by_id = {row[0]: {"title": row[1], "source_url": row[2]} for row in docs_result.all()}
            seen_docs: set = set()
            sources = []
            for chunk, _ in scored_chunks:
                if chunk.document_id not in seen_docs:
                    doc_info = docs_by_id.get(chunk.document_id, {})
                    if doc_info.get("source_url"):
                        sources.append(
                            {
                                "index": len(sources) + 1,
                                "title": doc_info.get("title") or f"Source {len(sources) + 1}",
                                "url": doc_info["source_url"],
                            }
                        )
                        seen_docs.add(chunk.document_id)

            api_key = openrouter_key
            if api_key is None and chatbot.byoak:
                try:
                    api_key = decrypt_api_key(chatbot.byoak)
                except Exception:
                    pass
            provider = "openrouter" if openrouter_key else chatbot.llm_provider
            client = get_llm_client(provider, api_key=api_key, base_url=openrouter_base_url)

            context_prompt = build_context_prompt(scored_chunks)
            system_prompt_text = build_system_prompt(chatbot)
            generated_answer = await client.generate(
                messages=[
                    {"role": "system", "content": system_prompt_text},
                    {"role": "user", "content": f"{context_prompt}\n\nUser question: {pair.question}"},
                ],
                model=chatbot.llm_model,
                temperature=0.0,
                max_tokens=500,
            )

            if escalated:
                status = "escalated"
            elif pair.answer:
                # LLM-as-judge: compare generated vs expected answer
                internal_model = await get_internal_model(db, pair.workspace_id)
                judge_client = get_internal_client()
                judge_prompt = (
                    f"Compare these two answers and determine if they convey the same information.\n"
                    f"Expected answer: {pair.answer}\n"
                    f"Generated answer: {generated_answer}\n\n"
                    f"Reply with PASS if the generated answer correctly addresses the question and is consistent "
                    f"with the expected answer, or FAIL if it does not. Reply with just one word."
                )
                verdict = await judge_client.generate(
                    messages=[{"role": "user", "content": judge_prompt}],
                    model=internal_model,
                    temperature=0.0,
                    max_tokens=10,
                )
                status = "passed" if "PASS" in verdict.strip().upper() else "failed"
            else:
                status = "passed"

            pair.status = status
            pair.confidence_score = confidence_score
            pair.sources = sources if sources else None
            pair.escalated = escalated
            pair.error_message = None
        except Exception as exc:
            logger.exception("test_qa_question failed for pair %s", qa_id)
            pair.status = "failed"
            pair.error_message = str(exc)[:300]

        await db.commit()


@register_job("suggest_qa_answer")
async def suggest_qa_answer(payload: dict):
    """Generate an AI-suggested answer for a QA pair using the knowledge base."""
    qa_id = uuid.UUID(payload["qa_id"])
    async with async_session_factory() as db:
        from app.models.knowledge import Chatbot, KnowledgeBase
        from app.models.organizational import Workspace
        from app.models.qa import QAPair
        from app.services.encryption import decrypt_api_key
        from app.services.llm import get_llm_client
        from app.services.rag import build_context_prompt, hybrid_search, rerank

        pair = (await db.execute(select(QAPair).where(QAPair.id == qa_id))).scalar_one_or_none()
        if not pair:
            return

        chatbot = (await db.execute(select(Chatbot).where(Chatbot.id == pair.chatbot_id))).scalar_one_or_none()
        if not chatbot:
            return

        kb = (
            await db.execute(select(KnowledgeBase).where(KnowledgeBase.chatbot_id == chatbot.id).limit(1))
        ).scalar_one_or_none()
        if not kb:
            return

        ws = (await db.execute(select(Workspace).where(Workspace.id == pair.workspace_id))).scalar_one_or_none()
        openrouter_key = None
        openrouter_base_url = None
        if ws:
            openrouter_base_url = ws.openrouter_base_url
            if ws.openrouter_api_key:
                try:
                    openrouter_key = decrypt_api_key(ws.openrouter_api_key)
                except Exception:
                    pass

        try:
            candidates = await hybrid_search(db, chatbot.workspace_id, kb.id, pair.question, top_k=10)
            if chatbot.use_reranking and candidates:
                scored_chunks = rerank(pair.question, candidates, top_k=5)
            else:
                scored_chunks = [(c, 0.5) for c in candidates[:5]]

            context_prompt = build_context_prompt(scored_chunks)
            api_key = openrouter_key
            if api_key is None and chatbot.byoak:
                try:
                    api_key = decrypt_api_key(chatbot.byoak)
                except Exception:
                    pass
            provider = "openrouter" if openrouter_key else chatbot.llm_provider
            client = get_llm_client(provider, api_key=api_key, base_url=openrouter_base_url)

            prompt = (
                f"{context_prompt}\n\n"
                f"Question: {pair.question}\n\n"
                f"Write a concise, accurate answer based only on the provided context."
            )
            suggested = await client.generate(
                messages=[{"role": "user", "content": prompt}],
                model=chatbot.llm_model,
                temperature=0.3,
                max_tokens=300,
            )
            pair.suggested_answer = suggested.strip()
            await db.commit()

            from app.realtime.events import notify_workspace

            await notify_workspace(
                str(pair.workspace_id),
                "qa:suggestion_ready",
                {
                    "qa_id": str(qa_id),
                    "chatbot_id": str(pair.chatbot_id),
                },
            )
        except Exception:
            logger.exception("suggest_qa_answer failed for pair %s", qa_id)


# --- Reindex article ---


@register_job("reindex_article")
async def reindex_article(payload: dict):
    article_id = uuid.UUID(payload["article_id"])
    async with async_session_factory() as db:
        from app.models.knowledge import Article, Document
        from app.services.ingestion import run_ingestion

        article = (await db.execute(select(Article).where(Article.id == article_id))).scalar_one_or_none()
        if not article or not article.body or not article.knowledge_base_id:
            return

        doc_result = await db.execute(
            select(Document).where(
                Document.knowledge_base_id == article.knowledge_base_id,
                Document.metadata_["source"].astext == "ai_draft",
                Document.title == article.title,
            )
        )
        doc = doc_result.scalar_one_or_none()
        if doc:
            doc.raw_content = article.body
            doc.status = "pending"
        else:
            doc = Document(
                workspace_id=article.workspace_id,
                knowledge_base_id=article.knowledge_base_id,
                source_type="text",
                raw_content=article.body,
                title=article.title,
                status="pending",
                metadata_={"source": "ai_draft"},
            )
            db.add(doc)

        await db.flush()
        await db.commit()
        await run_ingestion(db, doc.id)
        await db.commit()
