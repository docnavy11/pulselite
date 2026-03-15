import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.qa import QAPair


async def create_qa_pair(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    question: str,
    status_val: str = "pending",
) -> QAPair:
    pair = QAPair(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        chatbot_id=chatbot_id,
        question=question,
        status=status_val,
    )
    db.add(pair)
    await db.flush()
    return pair


async def list_qa_pairs(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
) -> tuple[list[QAPair], int]:
    base = select(QAPair).where(
        QAPair.workspace_id == workspace_id,
        QAPair.chatbot_id == chatbot_id,
    )
    if status_filter:
        base = base.where(QAPair.status == status_filter)

    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar() or 0

    query = base.order_by(QAPair.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = list(result.scalars().all())
    return items, total


async def get_qa_pair(db: AsyncSession, workspace_id: uuid.UUID, qa_pair_id: uuid.UUID) -> QAPair:
    result = await db.execute(
        select(QAPair).where(QAPair.id == qa_pair_id, QAPair.workspace_id == workspace_id)
    )
    pair = result.scalar_one_or_none()
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA pair not found")
    return pair


async def update_qa_pair(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    qa_pair_id: uuid.UUID,
    **kwargs,
) -> QAPair:
    pair = await get_qa_pair(db, workspace_id, qa_pair_id)
    for key, value in kwargs.items():
        setattr(pair, key, value)
    if "answer" in kwargs:
        pair.suggested_answer = None
    pair.is_edited = True
    await db.flush()
    await db.refresh(pair)
    return pair


async def delete_qa_pair(db: AsyncSession, workspace_id: uuid.UUID, qa_pair_id: uuid.UUID) -> None:
    pair = await get_qa_pair(db, workspace_id, qa_pair_id)
    await db.delete(pair)
    await db.flush()


async def get_testable_pair_ids(db: AsyncSession, chatbot_id: uuid.UUID) -> list[uuid.UUID]:
    """Return IDs of all completed/failed pairs that can be re-tested."""
    result = await db.execute(
        select(QAPair.id).where(
            QAPair.chatbot_id == chatbot_id,
            QAPair.status.in_(["completed", "failed"]),
        )
    )
    return [row[0] for row in result.all()]


async def reset_pairs_for_retest(
    db: AsyncSession, chatbot_id: uuid.UUID, pair_ids: list[uuid.UUID]
) -> None:
    """Reset pairs to testing state for batch re-test."""
    from sqlalchemy import update

    await db.execute(
        update(QAPair)
        .where(QAPair.id.in_(pair_ids), QAPair.chatbot_id == chatbot_id)
        .values(status="testing", answer=None, confidence_score=None, escalated=False, error_message=None)
    )


async def get_pending_pair_ids(db: AsyncSession, chatbot_id: uuid.UUID) -> list[uuid.UUID]:
    result = await db.execute(
        select(QAPair.id).where(
            QAPair.chatbot_id == chatbot_id,
            QAPair.status == "pending",
        )
    )
    return [row[0] for row in result.all()]


async def has_pending_pairs(db: AsyncSession, chatbot_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(func.count()).select_from(
            select(QAPair.id)
            .where(QAPair.chatbot_id == chatbot_id, QAPair.status.in_(["pending", "testing"]))
            .subquery()
        )
    )
    return (result.scalar() or 0) > 0


async def count_qa_pairs(db: AsyncSession, chatbot_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(
            select(QAPair.id).where(QAPair.chatbot_id == chatbot_id).subquery()
        )
    )
    return result.scalar() or 0


async def add_qa_to_kb(
    db: AsyncSession,
    pair: QAPair,
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> "Document":
    from app.models.knowledge import Document, KnowledgeBase

    # Find the chatbot's primary KB
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.chatbot_id == chatbot_id).limit(1)
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chatbot has no knowledge base")

    doc = Document(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        knowledge_base_id=kb.id,
        source_type="qa",
        title=pair.question,
        raw_content=f"Q: {pair.question}\nA: {pair.answer}",
        status="pending",
    )
    db.add(doc)
    pair.kb_document_id = doc.id
    await db.commit()  # Commit BEFORE dispatching Celery task

    from app.workers.tasks.ingest_document import ingest_document
    ingest_document.delay(str(doc.id))

    return doc
