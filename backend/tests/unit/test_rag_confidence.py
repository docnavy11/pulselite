import pytest
from unittest.mock import MagicMock


def _make_chunk(chunk_id="c1"):
    chunk = MagicMock()
    chunk.id = chunk_id
    return chunk


class TestComputeConfidence:
    def test_empty_chunks_returns_zeros(self):
        from app.services.rag.confidence import compute_confidence
        score, avg = compute_confidence([])
        assert score == 0.0
        assert avg == 0.0

    def test_single_chunk(self):
        from app.services.rag.confidence import compute_confidence
        scored = [(_make_chunk(), 0.85)]
        score, avg = compute_confidence(scored)
        assert score == 0.85
        assert avg == 0.85

    def test_multiple_chunks_max_and_avg(self):
        from app.services.rag.confidence import compute_confidence
        scored = [(_make_chunk("c1"), 0.9), (_make_chunk("c2"), 0.3), (_make_chunk("c3"), 0.6)]
        score, avg = compute_confidence(scored)
        assert score == 0.9
        assert avg == pytest.approx(0.6, abs=0.01)


class TestShouldEscalate:
    def test_below_threshold_escalates(self):
        from app.services.rag.confidence import should_escalate
        assert should_escalate(0.3, 0.5) is True

    def test_above_threshold_does_not_escalate(self):
        from app.services.rag.confidence import should_escalate
        assert should_escalate(0.7, 0.5) is False

    def test_equal_threshold_does_not_escalate(self):
        from app.services.rag.confidence import should_escalate
        assert should_escalate(0.5, 0.5) is False
