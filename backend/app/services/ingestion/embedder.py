import asyncio
import logging
import random

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

BATCH_SIZE = 100
MAX_RETRIES = 5
OPENAI_MODEL = "text-embedding-3-small"
OPENROUTER_MODEL = "openai/text-embedding-3-small"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _make_client() -> tuple[AsyncOpenAI, str]:
    """Return (client, model) preferring OpenRouter when its key is set."""
    if settings.OPENROUTER_API_KEY:
        return (
            AsyncOpenAI(api_key=settings.OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL),
            OPENROUTER_MODEL,
        )
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY), OPENAI_MODEL


async def embed_chunks(texts: list[str]) -> list[list[float]]:
    client, model = _make_client()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        embeddings = await _embed_with_retry(client, model, batch)
        all_embeddings.extend(embeddings)

    return all_embeddings


async def _embed_with_retry(client: AsyncOpenAI, model: str, texts: list[str]) -> list[list[float]]:
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.embeddings.create(model=model, input=texts)
            return [item.embedding for item in response.data]
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = (2**attempt) + random.uniform(0, 1)
            logger.warning(f"Embedding attempt {attempt + 1} failed: {e}. Retrying in {wait:.1f}s")
            await asyncio.sleep(wait)

    raise RuntimeError("Unreachable")
