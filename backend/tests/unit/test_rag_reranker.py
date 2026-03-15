import math
from unittest.mock import MagicMock, patch


def _make_chunk(content="text", chunk_id="c1"):
    chunk = MagicMock()
    chunk.id = chunk_id
    chunk.content = content
    return chunk


class TestSigmoid:
    def test_zero_returns_half(self):
        from app.services.rag.reranker import _sigmoid
        assert _sigmoid(0.0) == 0.5

    def test_large_positive_near_one(self):
        from app.services.rag.reranker import _sigmoid
        assert _sigmoid(10.0) > 0.99

    def test_large_negative_near_zero(self):
        from app.services.rag.reranker import _sigmoid
        assert _sigmoid(-10.0) < 0.01


class TestRerank:
    def test_empty_chunks_returns_empty(self):
        from app.services.rag.reranker import rerank
        assert rerank("query", []) == []

    def test_reranks_by_cross_encoder_score(self):
        from app.services.rag.reranker import rerank
        c1 = _make_chunk("low", "c1")
        c2 = _make_chunk("high", "c2")

        mock_model = MagicMock()
        # c2 gets higher raw score than c1
        mock_model.predict.return_value = [-2.0, 3.0]

        with patch("app.services.rag.reranker._get_model", return_value=mock_model):
            result = rerank("query", [c1, c2])

        # c2 should be first (higher sigmoid of 3.0)
        assert result[0][0].id == "c2"
        assert result[1][0].id == "c1"
        # Scores should be sigmoid-transformed
        assert result[0][1] > 0.9
        assert result[1][1] < 0.2

    def test_top_k_limits_results(self):
        from app.services.rag.reranker import rerank
        chunks = [_make_chunk(f"c{i}", f"c{i}") for i in range(5)]
        mock_model = MagicMock()
        mock_model.predict.return_value = [1.0, 2.0, 3.0, 4.0, 5.0]

        with patch("app.services.rag.reranker._get_model", return_value=mock_model):
            result = rerank("query", chunks, top_k=2)

        assert len(result) == 2
