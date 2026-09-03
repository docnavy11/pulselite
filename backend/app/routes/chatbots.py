"""Chatbot routes — list, create, detail, update, delete, widget config."""
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.knowledge import Chatbot, KnowledgeBase, Document

router = APIRouter()


@router.get("/chatbots", response_class=HTMLResponse)
async def list_chatbots(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(
        select(Chatbot).where(Chatbot.workspace_id == workspace.id, Chatbot.archived_at.is_(None))
        .order_by(Chatbot.created_at.desc())
    )
    chatbots = result.scalars().all()
    return request.app.state.templates.TemplateResponse("chatbots/list.html", {
        "request": request, "chatbots": chatbots,
    })


@router.get("/chatbots/new", response_class=HTMLResponse)
async def new_chatbot_page(request: Request):
    return request.app.state.templates.TemplateResponse("chatbots/new.html", {"request": request})


@router.post("/chatbots")
async def create_chatbot(
    request: Request, name: str = Form(...), url: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    chatbot = Chatbot(workspace_id=workspace.id, name=name)
    db.add(chatbot)
    await db.flush()

    if url:
        from app.services.crawl_service import prepare_crawl
        from app.background.runner import submit_job
        job_id, kb_id = await prepare_crawl(db, workspace.id, url, chatbot_id=chatbot.id)
        await submit_job("crawl_website", {"job_id": job_id})

    await db.commit()
    return RedirectResponse(f"/chatbots/{chatbot.id}", status_code=303)


@router.get("/chatbots/{chatbot_id}", response_class=HTMLResponse)
async def chatbot_detail(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(
        select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id)
    )
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)

    kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.chatbot_id == chatbot_id))
    kbs = kb_result.scalars().all()

    doc_count = 0
    if kbs:
        kb_ids = [kb.id for kb in kbs]
        count_result = await db.execute(
            select(func.count(Document.id)).where(Document.knowledge_base_id.in_(kb_ids))
        )
        doc_count = count_result.scalar_one()

    return request.app.state.templates.TemplateResponse("chatbots/detail.html", {
        "request": request, "chatbot": chatbot, "knowledge_bases": kbs, "doc_count": doc_count,
    })


@router.put("/chatbots/{chatbot_id}")
async def update_chatbot(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)
    form = await request.form()
    for key in ("name", "system_prompt", "tone", "language", "welcome_message", "fallback_message", "display_name"):
        if key in form:
            setattr(chatbot, key, form[key])
    await db.flush()
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/toast.html", {
            "request": request, "message": "Chatbot updated", "type": "success",
        })
    return RedirectResponse(f"/chatbots/{chatbot_id}", status_code=303)


@router.delete("/chatbots/{chatbot_id}")
async def delete_chatbot(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)
    await db.delete(chatbot)
    await db.flush()
    if request.headers.get("HX-Request"):
        return HTMLResponse("")  # HTMX removes the row
    return RedirectResponse("/chatbots", status_code=303)


@router.get("/chatbots/{chatbot_id}/sources", response_class=HTMLResponse)
async def chatbot_sources(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)
    kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.chatbot_id == chatbot_id))
    kbs = kb_result.scalars().all()
    docs = []
    if kbs:
        doc_result = await db.execute(
            select(Document).where(Document.knowledge_base_id.in_([kb.id for kb in kbs]))
            .order_by(Document.created_at.desc())
        )
        docs = doc_result.scalars().all()
    return request.app.state.templates.TemplateResponse("chatbots/sources.html", {
        "request": request, "chatbot": chatbot, "documents": docs, "knowledge_bases": kbs,
    })


@router.get("/chatbots/{chatbot_id}/deploy", response_class=HTMLResponse)
async def chatbot_deploy(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)
    return request.app.state.templates.TemplateResponse("chatbots/deploy.html", {
        "request": request, "chatbot": chatbot, "base_url": settings.BASE_URL,
    })


@router.get("/chatbots/{chatbot_id}/settings", response_class=HTMLResponse)
async def chatbot_settings(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    chatbot = result.scalar_one_or_none()
    if not chatbot:
        return HTMLResponse("Not found", status_code=404)
    return request.app.state.templates.TemplateResponse("chatbots/settings.html", {
        "request": request, "chatbot": chatbot,
    })
