import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


def _make_chunk(chunk_id=None):
    chunk = MagicMock()
    chunk.id = chunk_id or uuid.uuid4()
    return chunk


class TestReciprocalRankFusion:
    def test_empty_inputs(self):
        from app.services.rag.retriever import _reciprocal_rank_fusion
        result = _reciprocal_rank_fusion([], [], top_k=5)
        assert result == []

    def test_dense_only(self):
        from app.services.rag.retriever import _reciprocal_rank_fusion
        c1 = _make_chunk("c1")
        result = _reciprocal_rank_fusion([(c1, 0.9)], [], top_k=5)
        assert len(result) == 1
        assert result[0].id == "c1"

    def test_overlapping_chunks_get_higher_score(self):
        from app.services.rag.retriever import _reciprocal_rank_fusion
        shared = _make_chunk("shared")
        dense_only = _make_chunk("dense_only")
        sparse_only = _make_chunk("sparse_only")

        dense = [(shared, 0.9), (dense_only, 0.8)]
        sparse = [(shared, 5.0), (sparse_only, 3.0)]
        result = _reciprocal_rank_fusion(dense, sparse, top_k=3)

        # Shared chunk appears in both lists → highest RRF score
        assert result[0].id == "shared"

    def test_top_k_limits_output(self):
        from app.services.rag.retriever import _reciprocal_rank_fusion
        chunks = [(MagicMock(id=f"c{i}"), float(i)) for i in range(10)]
        result = _reciprocal_rank_fusion(chunks, [], top_k=3)
        assert len(result) == 3


class TestHybridSearch:
    @pytest.mark.asyncio
    async def test_combines_dense_and_sparse(self):
        from app.services.rag.retriever import hybrid_search

        c1 = _make_chunk("c1")
        c2 = _make_chunk("c2")

        with patch("app.services.rag.retriever._embed_query", new_callable=AsyncMock, return_value=[0.1] * 384), \
             patch("app.services.rag.retriever.dense_search", new_callable=AsyncMock, return_value=[(c1, 0.9)]), \
             patch("app.services.rag.retriever.sparse_search", new_callable=AsyncMock, return_value=[(c2, 5.0)]):

            db = AsyncMock()
            result = await hybrid_search(db, uuid.uuid4(), uuid.uuid4(), "test query", top_k=5)

        assert len(result) == 2  # both chunks from different sources
