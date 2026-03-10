import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace
from app.schemas.documents import DocumentCreate, DocumentResponse, DocumentUpdate
from app.services import document_service
from app.workers.tasks.ingest_document import ingest_document

router = APIRouter(prefix="/workspaces/{workspace_id}/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse)
async def create_document(
    body: DocumentCreate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    try:
        doc = await document_service.create_document(db, workspace_id, **body.model_dump())
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid knowledge_base_id or constraint violation"
        )
    ingest_document.delay(str(doc.id))
    return doc


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    knowledge_base_id: uuid.UUID,
    file: UploadFile = File(...),
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.create_document_from_upload(db, workspace_id, knowledge_base_id, file)
    await db.commit()
    ingest_document.delay(str(doc.id))
    return doc


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    knowledge_base_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.list_documents(db, workspace_id, knowledge_base_id)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    await document_service.delete_document(db, workspace_id, document_id)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: uuid.UUID,
    body: DocumentUpdate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.update_document(db, workspace_id, document_id, body.model_dump(exclude_none=True))
    await db.commit()
    return doc


@router.post("/{document_id}/reindex", response_model=DocumentResponse)
async def reindex_document(
    document_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.get_document(db, workspace_id, document_id)
    doc.status = "pending"
    await db.commit()
    ingest_document.delay(str(doc.id))
    return doc
