import uuid

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Chunk


async def insert_chunks(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    chunks: list[dict],
    embeddings: list[list[float]],
) -> int:
    for i, (chunk_data, embedding) in enumerate(zip(chunks, embeddings)):
        chunk = Chunk(
            workspace_id=workspace_id,
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            chunk_index=i,
            content=chunk_data["content"],
            heading_path=chunk_data.get("heading_path"),
            token_count=chunk_data.get("token_count"),
            embedding=embedding,
        )
        db.add(chunk)

    await db.flush()

    await db.execute(
        text(
            "UPDATE chunks SET search_vector = to_tsvector('english', content) "
            "WHERE document_id = :doc_id AND search_vector IS NULL"
        ),
        {"doc_id": str(document_id)},
    )

    return len(chunks)


async def delete_by_document(db: AsyncSession, document_id: uuid.UUID) -> int:
    result = await db.execute(delete(Chunk).where(Chunk.document_id == document_id))
    return result.rowcount


async def similarity_search(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[Chunk]:
    result = await db.execute(
        select(Chunk)
        .where(
            Chunk.workspace_id == workspace_id,
            Chunk.knowledge_base_id == knowledge_base_id,
        )
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    return list(result.scalars().all())


async def hybrid_search(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    query_embedding: list[float],
    query_text: str,
    top_k: int = 5,
) -> list[Chunk]:
    ts_query = func.plainto_tsquery("english", query_text)
    result = await db.execute(
        select(Chunk)
        .where(
            Chunk.workspace_id == workspace_id,
            Chunk.knowledge_base_id == knowledge_base_id,
            Chunk.search_vector.op("@@")(ts_query),
        )
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    return list(result.scalars().all())
