"""Document management routes — upload, create, delete, reindex."""

import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.knowledge import Document, KnowledgeBase

router = APIRouter()


@router.post("/chatbots/{chatbot_id}/sources/url")
async def add_url_source(
    request: Request,
    chatbot_id: uuid.UUID,
    url: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    kb = await _get_or_create_kb(db, workspace.id, chatbot_id)
    doc = Document(
        workspace_id=workspace.id,
        knowledge_base_id=kb.id,
        source_type="url",
        source_url=url,
        title=url,
        status="pending",
    )
    db.add(doc)
    await db.flush()
    await db.commit()

    from app.background.runner import submit_job

    await submit_job("ingest_document", {"document_id": str(doc.id)})

    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/document_row.html",
            {
                "request": request,
                "doc": doc,
            },
        )
    return RedirectResponse(f"/chatbots/{chatbot_id}/sources", status_code=303)


@router.post("/chatbots/{chatbot_id}/sources/text")
async def add_text_source(
    request: Request,
    chatbot_id: uuid.UUID,
    title: str = Form(...),
    content: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    kb = await _get_or_create_kb(db, workspace.id, chatbot_id)
    doc = Document(
        workspace_id=workspace.id,
        knowledge_base_id=kb.id,
        source_type="text",
        raw_content=content,
        title=title,
        status="pending",
    )
    db.add(doc)
    await db.flush()
    await db.commit()

    from app.background.runner import submit_job

    await submit_job("ingest_document", {"document_id": str(doc.id)})

    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/document_row.html",
            {
                "request": request,
                "doc": doc,
            },
        )
    return RedirectResponse(f"/chatbots/{chatbot_id}/sources", status_code=303)


@router.post("/chatbots/{chatbot_id}/sources/upload")
async def upload_file_source(
    request: Request,
    chatbot_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    kb = await _get_or_create_kb(db, workspace.id, chatbot_id)

    import os

    upload_dir = "/app/data/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or "")[1]
    file_path = os.path.join(upload_dir, f"{file_id}{ext}")
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    doc = Document(
        workspace_id=workspace.id,
        knowledge_base_id=kb.id,
        source_type="file",
        file_path=file_path,
        title=file.filename or "Uploaded file",
        status="pending",
    )
    db.add(doc)
    await db.flush()
    await db.commit()

    from app.background.runner import submit_job

    await submit_job("ingest_document", {"document_id": str(doc.id)})

    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/document_row.html",
            {
                "request": request,
                "doc": doc,
            },
        )
    return RedirectResponse(f"/chatbots/{chatbot_id}/sources", status_code=303)


@router.delete("/documents/{document_id}")
async def delete_document(request: Request, document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Document).where(Document.id == document_id, Document.workspace_id == workspace.id))
    doc = result.scalar_one_or_none()
    if doc:
        from app.services.ingestion.vector_store import delete_by_document

        await delete_by_document(db, doc.id)
        await db.delete(doc)
        await db.flush()
    return HTMLResponse("")


@router.put("/documents/{document_id}/sync-frequency")
async def update_sync_frequency(
    request: Request,
    document_id: uuid.UUID,
    sync_frequency: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    result = await db.execute(select(Document).where(Document.id == document_id, Document.workspace_id == workspace.id))
    doc = result.scalar_one_or_none()
    if doc and sync_frequency in ("manual", "daily", "weekly", "monthly"):
        doc.sync_frequency = sync_frequency
        await db.flush()
    return HTMLResponse("")


@router.post("/documents/{document_id}/reindex")
async def reindex_document(request: Request, document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Document).where(Document.id == document_id, Document.workspace_id == workspace.id))
    doc = result.scalar_one_or_none()
    if doc:
        doc.status = "pending"
        doc.content_hash = None
        await db.flush()
        await db.commit()
        from app.background.runner import submit_job

        await submit_job("ingest_document", {"document_id": str(doc.id)})
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "message": "Reindexing...",
                "type": "success",
            },
        )
    return HTMLResponse("OK")


async def _get_or_create_kb(db, workspace_id, chatbot_id):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.chatbot_id == chatbot_id).limit(1))
    kb = result.scalar_one_or_none()
    if not kb:
        kb = KnowledgeBase(workspace_id=workspace_id, chatbot_id=chatbot_id, name="Default")
        db.add(kb)
        await db.flush()
    return kb
