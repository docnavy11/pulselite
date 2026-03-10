import uuid

from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.knowledge import Chunk

DENSE_CANDIDATES = 20
SPARSE_CANDIDATES = 20
RRF_K = 60


async def dense_search(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    query_embedding: list[float],
    limit: int = DENSE_CANDIDATES,
) -> list[tuple[Chunk, float]]:
    distance = Chunk.embedding.cosine_distance(query_embedding)
    result = await db.execute(
        select(Chunk, distance.label("distance"))
        .where(
            Chunk.workspace_id == workspace_id,
            Chunk.knowledge_base_id == knowledge_base_id,
            Chunk.embedding.isnot(None),
        )
        .order_by(distance)
        .limit(limit)
    )
    rows = result.all()
    return [(row[0], 1.0 - row[1]) for row in rows]


async def sparse_search(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    query_text: str,
    limit: int = SPARSE_CANDIDATES,
) -> list[tuple[Chunk, float]]:
    ts_query = func.plainto_tsquery("english", query_text)
    rank = func.ts_rank_cd(Chunk.search_vector, ts_query)
    result = await db.execute(
        select(Chunk, rank.label("rank"))
        .where(
            Chunk.workspace_id == workspace_id,
            Chunk.knowledge_base_id == knowledge_base_id,
            Chunk.search_vector.op("@@")(ts_query),
        )
        .order_by(rank.desc())
        .limit(limit)
    )
    return list(result.all())


async def hybrid_search(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    query_text: str,
    top_k: int = 10,
) -> list[Chunk]:
    query_embedding = await _embed_query(query_text)

    dense_results = await dense_search(db, workspace_id, knowledge_base_id, query_embedding)
    sparse_results = await sparse_search(db, workspace_id, knowledge_base_id, query_text)

    return _reciprocal_rank_fusion(dense_results, sparse_results, top_k)


def _reciprocal_rank_fusion(
    dense_results: list[tuple[Chunk, float]],
    sparse_results: list[tuple[Chunk, float]],
    top_k: int,
) -> list[Chunk]:
    scores: dict[uuid.UUID, float] = {}
    chunk_map: dict[uuid.UUID, Chunk] = {}

    for rank, (chunk, _score) in enumerate(dense_results):
        chunk_id = chunk.id
        chunk_map[chunk_id] = chunk
        scores[chunk_id] = scores.get(chunk_id, 0) + 1.0 / (RRF_K + rank + 1)

    for rank, (chunk, _score) in enumerate(sparse_results):
        chunk_id = chunk.id
        chunk_map[chunk_id] = chunk
        scores[chunk_id] = scores.get(chunk_id, 0) + 1.0 / (RRF_K + rank + 1)

    sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:top_k]
    return [chunk_map[cid] for cid in sorted_ids]


async def _embed_query(query: str) -> list[float]:
    if settings.OPENROUTER_API_KEY:
        client = AsyncOpenAI(api_key=settings.OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")
        model = "openai/text-embedding-3-small"
    else:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        model = "text-embedding-3-small"
    response = await client.embeddings.create(model=model, input=[query])
    return response.data[0].embedding
