import logging
import math
from functools import lru_cache

from app.models.knowledge import Chunk

logger = logging.getLogger(__name__)

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _get_model():
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        logger.warning(
            "sentence-transformers is not installed — reranking disabled. "
            "Install with: pip install sentence-transformers (included in the worker image)."
        )
        return None

    logger.info(f"Loading reranker model: {MODEL_NAME}")
    return CrossEncoder(MODEL_NAME)


def _sigmoid(x: float) -> float:
    """Convert raw cross-encoder logit to 0-1 probability."""
    return 1.0 / (1.0 + math.exp(-x))


def rerank(query: str, chunks: list[Chunk], top_k: int | None = None) -> list[tuple[Chunk, float]]:
    if not chunks:
        return []

    model = _get_model()
    if model is None:
        # Graceful fallback: return chunks in original order with neutral scores
        scored = [(chunk, 0.5) for chunk in chunks]
        return scored[:top_k] if top_k else scored
    pairs = [(query, chunk.content) for chunk in chunks]
    scores = model.predict(pairs)

    scored = list(zip(chunks, [_sigmoid(float(s)) for s in scores]))
    scored.sort(key=lambda x: x[1], reverse=True)

    if top_k:
        scored = scored[:top_k]

    return scored
