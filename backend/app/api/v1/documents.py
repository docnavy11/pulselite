import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace
from sqlalchemy import select

from app.models.knowledge import Chunk
from app.schemas.documents import DocumentCreate, DocumentContentResponse, DocumentResponse, DocumentUpdate, ChunkResponse
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
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0, le=10_000),
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.list_documents(db, workspace_id, knowledge_base_id, limit=limit, offset=offset)


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


@router.get("/{document_id}/content", response_model=DocumentContentResponse)
async def get_document_content(
    document_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.get_document(db, workspace_id, document_id)
    chunk_result = await db.execute(
        select(Chunk)
        .where(Chunk.document_id == doc.id)
        .order_by(Chunk.chunk_index)
    )
    chunks = chunk_result.scalars().all()
    return DocumentContentResponse(
        id=doc.id,
        title=doc.title,
        source_type=doc.source_type,
        source_url=doc.source_url,
        status=doc.status,
        error_message=doc.error_message,
        char_count=doc.char_count,
        chunk_count=doc.chunk_count,
        raw_content=doc.raw_content,
        chunks=[ChunkResponse.model_validate(c) for c in chunks],
        ingestion_steps=doc.ingestion_steps,
        last_indexed_at=doc.last_indexed_at,
    )


@router.post("/{document_id}/reindex", response_model=DocumentResponse)
async def reindex_document(
    document_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    doc = await document_service.get_document(db, workspace_id, document_id)
    doc.status = "pending"
    await db.commit()
    await db.refresh(doc)
    ingest_document.delay(str(doc.id))
    return doc
