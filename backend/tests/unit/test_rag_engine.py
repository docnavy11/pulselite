import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


def _make_chatbot(**overrides):
    cb = MagicMock()
    cb.id = uuid.uuid4()
    cb.workspace_id = uuid.uuid4()
    cb.use_reranking = overrides.get("use_reranking", False)
    cb.retrieval_top_k = overrides.get("retrieval_top_k", 5)
    cb.confidence_threshold = overrides.get("confidence_threshold", 0.4)
    cb.llm_provider = "openrouter"
    cb.llm_model = "openai/gpt-4o-mini"
    cb.temperature = 0.7
    cb.max_tokens = 1024
    cb.name = "TestBot"
    cb.display_name = "Test"
    cb.tone = "professional"
    cb.language = "English"
    cb.auto_detect_language = False
    cb.system_prompt = "Be helpful."
    cb.byoak = None
    return cb


def _make_kb():
    kb = MagicMock()
    kb.id = uuid.uuid4()
    return kb


def _make_chunk(chunk_id=None, content="test content", doc_id=None):
    chunk = MagicMock()
    chunk.id = chunk_id or uuid.uuid4()
    chunk.content = content
    chunk.document_id = doc_id or uuid.uuid4()
    chunk.heading_path = "FAQ"
    return chunk


class TestProcessQuery:
    @pytest.mark.asyncio
    async def test_no_knowledge_base_yields_escalation(self):
        from app.services.rag.engine import process_query, RAGResult

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # no KB
        db.execute = AsyncMock(return_value=mock_result)

        items = []
        async for item in process_query(db, "How do I login?", _make_chatbot()):
            items.append(item)

        # Should yield RAGResult with escalated=True, then a fallback message
        rag_results = [i for i in items if isinstance(i, RAGResult)]
        assert len(rag_results) == 1
        assert rag_results[0].escalated is True
        assert rag_results[0].confidence_score == 0.0

        text_items = [i for i in items if isinstance(i, str)]
        assert any("knowledge base" in t.lower() for t in text_items)

    @pytest.mark.asyncio
    async def test_with_kb_retrieves_and_generates(self):
        from app.services.rag.engine import process_query, RAGResult

        kb = _make_kb()
        chunk = _make_chunk()
        doc_id = chunk.document_id

        # Mock DB: first call returns KB, second call returns doc metadata
        kb_result = MagicMock()
        kb_result.scalar_one_or_none.return_value = kb

        doc_row = MagicMock()
        doc_row.__getitem__ = lambda self, key: {0: doc_id, 1: "My Doc", 2: "https://example.com"}[key]
        docs_result = MagicMock()
        docs_result.all.return_value = [doc_row]

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[kb_result, docs_result])

        async def fake_stream(*args, **kwargs):
            yield "Generated answer"
            yield {"prompt_tokens": 50, "completion_tokens": 20}

        with patch("app.services.rag.engine.hybrid_search", new_callable=AsyncMock, return_value=[chunk]), \
             patch("app.services.rag.engine.compute_confidence", return_value=(0.85, 0.7)), \
             patch("app.services.rag.engine.should_escalate", return_value=False), \
             patch("app.services.rag.engine.get_conversation_history", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.rag.engine.stream_response", side_effect=fake_stream):

            items = []
            async for item in process_query(db, "test query", _make_chatbot(), conversation_id=uuid.uuid4()):
                items.append(item)

        rag_results = [i for i in items if isinstance(i, RAGResult)]
        assert len(rag_results) == 1
        assert rag_results[0].confidence_score == 0.85
        assert rag_results[0].escalated is False

        text_items = [i for i in items if isinstance(i, str)]
        assert "Generated answer" in text_items

    @pytest.mark.asyncio
    async def test_reranking_enabled(self):
        from app.services.rag.engine import process_query

        kb = _make_kb()
        chunk = _make_chunk()

        kb_result = MagicMock()
        kb_result.scalar_one_or_none.return_value = kb
        docs_result = MagicMock()
        docs_result.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[kb_result, docs_result])

        async def fake_stream(*args, **kwargs):
            yield "answer"

        with patch("app.services.rag.engine.hybrid_search", new_callable=AsyncMock, return_value=[chunk]), \
             patch("app.services.rag.engine.rerank", return_value=[(chunk, 0.9)]) as mock_rerank, \
             patch("app.services.rag.engine.compute_confidence", return_value=(0.9, 0.9)), \
             patch("app.services.rag.engine.should_escalate", return_value=False), \
             patch("app.services.rag.engine.get_conversation_history", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.rag.engine.stream_response", side_effect=fake_stream):

            async for _ in process_query(db, "test", _make_chatbot(use_reranking=True)):
                pass

        mock_rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_retry(self):
        """When initial confidence is below threshold, reformulate + re-search + rerank."""
        from app.services.rag.engine import process_query, RAGResult

        kb = _make_kb()
        original_chunk = _make_chunk("orig")
        retry_chunk = _make_chunk("retry", content="better content")

        kb_result = MagicMock()
        kb_result.scalar_one_or_none.return_value = kb
        docs_result = MagicMock()
        docs_result.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[kb_result, docs_result])

        # First hybrid_search returns original chunk, retry searches return new chunk
        search_calls = [
            [original_chunk],         # original search
            [retry_chunk],            # reformulated query 1
            [],                       # reformulated query 2
            [],                       # reformulated query 3
        ]
        search_call_idx = {"i": 0}

        async def mock_hybrid_search(*args, **kwargs):
            idx = search_call_idx["i"]
            search_call_idx["i"] += 1
            return search_calls[idx]

        async def fake_stream(*args, **kwargs):
            yield "answer"

        with patch("app.services.rag.engine.hybrid_search", side_effect=mock_hybrid_search), \
             patch("app.services.rag.engine.compute_confidence") as mock_conf, \
             patch("app.services.rag.engine.should_escalate") as mock_esc, \
             patch("app.services.rag.engine.rerank", return_value=[(retry_chunk, 0.85), (original_chunk, 0.4)]) as mock_rerank, \
             patch("app.services.rag.engine.reformulate_queries", new_callable=AsyncMock, return_value=["q1", "q2", "q3"]), \
             patch("app.services.rag.engine.get_conversation_history", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.rag.engine.stream_response", side_effect=fake_stream):

            # First confidence check: low → triggers retry
            # Second confidence check (after retry): high
            mock_conf.side_effect = [(0.2, 0.2), (0.85, 0.6)]
            mock_esc.side_effect = [True, False]

            items = []
            async for item in process_query(db, "test query", _make_chatbot()):
                items.append(item)

        # Rerank was called on merged chunks (always reranks on retry)
        mock_rerank.assert_called_once()
        # RAGResult should reflect retry success
        rag_results = [i for i in items if isinstance(i, RAGResult)]
        assert rag_results[0].retried is True
        assert rag_results[0].original_confidence_low is True
        assert rag_results[0].escalated is False

    @pytest.mark.asyncio
    async def test_retry_still_escalates_when_confidence_stays_low(self):
        """When retry doesn't improve confidence, still escalates."""
        from app.services.rag.engine import process_query, RAGResult

        kb = _make_kb()
        chunk = _make_chunk("c1")

        kb_result = MagicMock()
        kb_result.scalar_one_or_none.return_value = kb
        docs_result = MagicMock()
        docs_result.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[kb_result, docs_result])

        async def mock_hybrid_search(*args, **kwargs):
            return [chunk]

        async def fake_stream(*args, **kwargs):
            yield "fallback answer"

        with patch("app.services.rag.engine.hybrid_search", side_effect=mock_hybrid_search), \
             patch("app.services.rag.engine.compute_confidence", return_value=(0.2, 0.2)), \
             patch("app.services.rag.engine.should_escalate", return_value=True), \
             patch("app.services.rag.engine.rerank", return_value=[(chunk, 0.15)]), \
             patch("app.services.rag.engine.reformulate_queries", new_callable=AsyncMock, return_value=["q1", "q2", "q3"]), \
             patch("app.services.rag.engine.get_conversation_history", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.rag.engine.stream_response", side_effect=fake_stream):

            items = []
            async for item in process_query(db, "test", _make_chatbot()):
                items.append(item)

        rag_results = [i for i in items if isinstance(i, RAGResult)]
        assert rag_results[0].retried is True
        assert rag_results[0].original_confidence_low is True
        assert rag_results[0].escalated is True

    @pytest.mark.asyncio
    async def test_reformulation_failure_proceeds_without_retry(self):
        """When reformulate_queries returns empty list, no retry happens."""
        from app.services.rag.engine import process_query, RAGResult

        kb = _make_kb()
        chunk = _make_chunk("c1")

        kb_result = MagicMock()
        kb_result.scalar_one_or_none.return_value = kb
        docs_result = MagicMock()
        docs_result.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[kb_result, docs_result])

        async def fake_stream(*args, **kwargs):
            yield "answer"

        with patch("app.services.rag.engine.hybrid_search", new_callable=AsyncMock, return_value=[chunk]), \
             patch("app.services.rag.engine.compute_confidence", return_value=(0.2, 0.2)), \
             patch("app.services.rag.engine.should_escalate", return_value=True), \
             patch("app.services.rag.engine.reformulate_queries", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.rag.engine.get_conversation_history", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.rag.engine.stream_response", side_effect=fake_stream):

            items = []
            async for item in process_query(db, "test", _make_chatbot()):
                items.append(item)

        rag_results = [i for i in items if isinstance(i, RAGResult)]
        assert rag_results[0].retried is False
        assert rag_results[0].original_confidence_low is True
        assert rag_results[0].escalated is True

    @pytest.mark.asyncio
    async def test_retry_deduplicates_chunks(self):
        """Chunks appearing in multiple search results are not duplicated."""
        from app.services.rag.engine import process_query, RAGResult

        kb = _make_kb()
        shared_chunk = _make_chunk("shared")
        unique_chunk = _make_chunk("unique")

        kb_result = MagicMock()
        kb_result.scalar_one_or_none.return_value = kb
        docs_result = MagicMock()
        docs_result.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[kb_result, docs_result])

        search_calls = [
            [shared_chunk],                   # original
            [shared_chunk, unique_chunk],      # retry query 1 (shared appears again)
        ]
        search_call_idx = {"i": 0}

        async def mock_hybrid_search(*args, **kwargs):
            idx = search_call_idx["i"]
            search_call_idx["i"] += 1
            return search_calls[idx] if idx < len(search_calls) else []

        async def fake_stream(*args, **kwargs):
            yield "answer"

        with patch("app.services.rag.engine.hybrid_search", side_effect=mock_hybrid_search), \
             patch("app.services.rag.engine.compute_confidence") as mock_conf, \
             patch("app.services.rag.engine.should_escalate") as mock_esc, \
             patch("app.services.rag.engine.rerank") as mock_rerank, \
             patch("app.services.rag.engine.reformulate_queries", new_callable=AsyncMock, return_value=["q1"]), \
             patch("app.services.rag.engine.get_conversation_history", new_callable=AsyncMock, return_value=[]), \
             patch("app.services.rag.engine.stream_response", side_effect=fake_stream):

            mock_conf.side_effect = [(0.2, 0.2), (0.8, 0.8)]
            mock_esc.side_effect = [True, False]
            mock_rerank.return_value = [(shared_chunk, 0.9), (unique_chunk, 0.7)]

            items = []
            async for item in process_query(db, "test", _make_chatbot()):
                items.append(item)

        # rerank should receive exactly 2 chunks (deduplicated), not 3
        rerank_call_chunks = mock_rerank.call_args[0][1]
        chunk_ids = [c.id for c in rerank_call_chunks]
        assert len(chunk_ids) == 2
        assert "shared" in chunk_ids
        assert "unique" in chunk_ids
