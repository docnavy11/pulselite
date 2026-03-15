import logging
import math
from functools import lru_cache

from app.models.knowledge import Chunk

logger = logging.getLogger(__name__)

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import CrossEncoder

    logger.info(f"Loading reranker model: {MODEL_NAME}")
    return CrossEncoder(MODEL_NAME)


def _sigmoid(x: float) -> float:
    """Convert raw cross-encoder logit to 0-1 probability."""
    return 1.0 / (1.0 + math.exp(-x))


def rerank(query: str, chunks: list[Chunk], top_k: int | None = None) -> list[tuple[Chunk, float]]:
    if not chunks:
        return []

    model = _get_model()
    pairs = [(query, chunk.content) for chunk in chunks]
    scores = model.predict(pairs)

    scored = list(zip(chunks, [_sigmoid(float(s)) for s in scores]))
    scored.sort(key=lambda x: x[1], reverse=True)

    if top_k:
        scored = scored[:top_k]

    return scored
