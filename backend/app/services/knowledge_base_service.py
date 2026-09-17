import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document, KnowledgeBase


async def create_knowledge_base(db: AsyncSession, workspace_id: uuid.UUID, **kwargs) -> KnowledgeBase:
    kb = KnowledgeBase(workspace_id=workspace_id, **kwargs)
    db.add(kb)
    await db.flush()
    return kb


async def list_knowledge_bases(
    db: AsyncSession, workspace_id: uuid.UUID, chatbot_id: uuid.UUID | None = None
) -> list[KnowledgeBase]:
    query = select(KnowledgeBase).where(KnowledgeBase.workspace_id == workspace_id)
    if chatbot_id:
        query = query.where(KnowledgeBase.chatbot_id == chatbot_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_knowledge_base(db: AsyncSession, workspace_id: uuid.UUID, kb_id: uuid.UUID) -> KnowledgeBase:
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.workspace_id == workspace_id)
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return kb


async def delete_knowledge_base(db: AsyncSession, workspace_id: uuid.UUID, kb_id: uuid.UUID) -> None:
    kb = await get_knowledge_base(db, workspace_id, kb_id)

    # Sum char_count of all documents in this KB and release from workspace budget
    total_result = await db.execute(
        select(func.coalesce(func.sum(Document.char_count), 0)).where(Document.knowledge_base_id == kb_id)
    )
    total_chars = total_result.scalar() or 0
    if total_chars > 0:
        await db.execute(
            sa_text("""
                UPDATE workspaces
                SET chars_indexed = GREATEST(0, chars_indexed - :n)
                WHERE id = :workspace_id
            """),
            {"n": total_chars, "workspace_id": workspace_id},
        )

    # Delete documents first (FK constraint), then the KB
    docs_result = await db.execute(select(Document).where(Document.knowledge_base_id == kb_id))
    for doc in docs_result.scalars().all():
        await db.delete(doc)
    await db.flush()

    await db.delete(kb)
    await db.flush()
