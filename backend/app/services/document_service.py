import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document

UPLOAD_DIR = "/app/uploads"
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".csv", ".txt", ".md", ".html"}


async def create_document(db: AsyncSession, workspace_id: uuid.UUID, **kwargs) -> Document:
    doc = Document(workspace_id=workspace_id, **kwargs)
    db.add(doc)
    await db.flush()
    return doc


async def create_document_from_upload(
    db: AsyncSession, workspace_id: uuid.UUID, knowledge_base_id: uuid.UUID, file: UploadFile
) -> Document:
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    safe_name = os.path.basename(file.filename or "upload")
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large (max 50MB)")
    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base_id,
        source_type="file",
        file_path=file_path,
        title=safe_name,
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
    ALLOWED_UPDATE_FIELDS = {"title", "sync_frequency"}
    for key, value in updates.items():
        if key in ALLOWED_UPDATE_FIELDS:
            setattr(doc, key, value)
    if "sync_frequency" in updates:
        freq_days = {"daily": 1, "weekly": 7, "monthly": 30}
        if updates["sync_frequency"] in freq_days:
            doc.next_sync_at = datetime.now(timezone.utc) + timedelta(days=freq_days[updates["sync_frequency"]])
        else:
            doc.next_sync_at = None
    return doc
