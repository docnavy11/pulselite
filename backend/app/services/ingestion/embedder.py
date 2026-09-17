import asyncio
import logging

from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
BATCH_SIZE = 256

# Lazy-loaded singleton — model downloads on first use (~32MB)
_model: TextEmbedding | None = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        logger.info("Loading local embedding model: %s", MODEL_NAME)
        _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


async def embed_chunks(texts: list[str]) -> list[list[float]]:
    """Embed texts using local ONNX model. Runs in thread to avoid blocking the event loop."""
    model = _get_model()
    embeddings = await asyncio.to_thread(lambda: [e.tolist() for e in model.embed(texts, batch_size=BATCH_SIZE)])
    return embeddings
