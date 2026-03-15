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
