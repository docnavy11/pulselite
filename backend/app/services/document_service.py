import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document

UPLOAD_DIR = "/app/uploads"


async def create_document(db: AsyncSession, workspace_id: uuid.UUID, **kwargs) -> Document:
    doc = Document(workspace_id=workspace_id, **kwargs)
    db.add(doc)
    await db.flush()
    return doc


async def create_document_from_upload(
    db: AsyncSession, workspace_id: uuid.UUID, knowledge_base_id: uuid.UUID, file: UploadFile
) -> Document:
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_type="file",
        file_path=file_path,
        title=filename,
    )
    db.add(doc)
    await db.flush()
    return doc


async def list_documents(db: AsyncSession, workspace_id: uuid.UUID, knowledge_base_id: uuid.UUID) -> list[Document]:
    result = await db.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.knowledge_base_id == knowledge_base_id,
        )
    )
    return list(result.scalars().all())


async def get_document(db: AsyncSession, workspace_id: uuid.UUID, document_id: uuid.UUID) -> Document:
    result = await db.execute(select(Document).where(Document.id == document_id, Document.workspace_id == workspace_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


async def delete_document(db: AsyncSession, workspace_id: uuid.UUID, document_id: uuid.UUID) -> None:
    doc = await get_document(db, workspace_id, document_id)
    await db.delete(doc)
    await db.flush()


async def update_document(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    updates: dict,
) -> Document:
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    for key, value in updates.items():
        setattr(doc, key, value)
    if "sync_frequency" in updates:
        freq_days = {"daily": 1, "weekly": 7, "monthly": 30}
        if updates["sync_frequency"] in freq_days:
            doc.next_sync_at = datetime.now(timezone.utc) + timedelta(days=freq_days[updates["sync_frequency"]])
        else:
            doc.next_sync_at = None
    return doc
