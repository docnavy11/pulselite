"""Crawl routes — start crawl, view status."""

import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.knowledge import Chatbot, CrawlJob
from app.services.crawl_service import prepare_crawl

router = APIRouter()


@router.post("/chatbots/{chatbot_id}/crawl")
async def start_crawl(
    request: Request,
    chatbot_id: uuid.UUID,
    url: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    include_paths = []
    exclude_paths = []
    form = await request.form()
    if "include_paths" in form and form["include_paths"]:
        include_paths = [p.strip() for p in form["include_paths"].split(",") if p.strip()]
    if "exclude_paths" in form and form["exclude_paths"]:
        exclude_paths = [p.strip() for p in form["exclude_paths"].split(",") if p.strip()]

    workspace = request.state.workspace
    job_id, kb_id = await prepare_crawl(
        db, workspace.id, url, include_paths=include_paths, exclude_paths=exclude_paths, chatbot_id=chatbot_id
    )
    from app.background.runner import submit_job

    await submit_job("crawl_website", {"job_id": job_id})

    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/crawl_progress.html",
            {
                "request": request,
                "chatbot_id": chatbot_id,
                "job_id": job_id,
                "status": "pending",
            },
        )
    return RedirectResponse(f"/chatbots/{chatbot_id}/sources", status_code=303)


@router.post("/chatbots/{chatbot_id}/crawl/preview", response_class=HTMLResponse)
async def preview_crawl(
    request: Request,
    chatbot_id: uuid.UUID,
    url: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    # Verify chatbot belongs to workspace
    result = await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace.id))
    if not result.scalar_one_or_none():
        return HTMLResponse("Not found", status_code=404)

    from urllib.parse import urlparse

    from app.services.crawler import discover_urls

    try:
        discovered = await discover_urls(url.strip(), [], [])
    except Exception as exc:
        return request.app.state.templates.TemplateResponse(
            "components/crawl_preview.html",
            {
                "request": request,
                "error": str(exc),
                "url": url,
            },
        )

    if not discovered:
        return request.app.state.templates.TemplateResponse(
            "components/crawl_preview.html",
            {
                "request": request,
                "error": "No pages found. Check the URL and try again.",
                "url": url,
            },
        )

    # Build path-prefix groups (2 levels deep)
    path_counts: dict[str, int] = {}
    for d in discovered:
        try:
            path = urlparse(d.url).path
            segments = [s for s in path.split("/") if s]
            if not segments:
                key = "/"
            elif len(segments) == 1:
                key = "/" + segments[0]
            else:
                key = "/" + segments[0] + "/" + segments[1]
            path_counts[key] = path_counts.get(key, 0) + 1
        except Exception:
            pass

    # Roll up: group level-2 paths under their level-1 parent
    level1: dict[str, dict] = {}
    for path, count in sorted(path_counts.items()):
        parts = [s for s in path.split("/") if s]
        if not parts:
            key = "/"
        else:
            key = "/" + parts[0]

        if len(parts) <= 1:
            if key not in level1:
                level1[key] = {"label": key, "count": 0, "children": {}}
            level1[key]["count"] += count
        else:
            parent_key = "/" + parts[0]
            if parent_key not in level1:
                level1[parent_key] = {"label": parent_key, "count": 0, "children": {}}
            child_key = path
            level1[parent_key]["children"][child_key] = {"label": "/" + parts[1], "count": count}

    return request.app.state.templates.TemplateResponse(
        "components/crawl_preview.html",
        {
            "request": request,
            "url": url,
            "chatbot_id": chatbot_id,
            "total": len(discovered),
            "groups": level1,
        },
    )


@router.post("/chatbots/{chatbot_id}/retry-failed")
async def retry_failed(request: Request, chatbot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    from app.background.runner import submit_job
    from app.models.knowledge import Document, KnowledgeBase

    kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.chatbot_id == chatbot_id))
    kbs = kb_result.scalars().all()
    count = 0
    if kbs:
        docs = (
            (
                await db.execute(
                    select(Document).where(
                        Document.knowledge_base_id.in_([kb.id for kb in kbs]), Document.status == "failed"
                    )
                )
            )
            .scalars()
            .all()
        )
        for doc in docs:
            doc.status = "pending"
            doc.content_hash = None
            await db.flush()
            await submit_job("ingest_document", {"document_id": str(doc.id)})
            count += 1
    await db.commit()
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse(
            "components/toast.html",
            {
                "request": request,
                "message": f"Retrying {count} failed documents",
                "type": "success",
            },
        )
    return RedirectResponse(f"/chatbots/{chatbot_id}/sources", status_code=303)


@router.get("/chatbots/{chatbot_id}/crawl/{job_id}", response_class=HTMLResponse)
async def crawl_status(request: Request, chatbot_id: uuid.UUID, job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    result = await db.execute(select(CrawlJob).where(CrawlJob.id == job_id, CrawlJob.workspace_id == workspace.id))
    job = result.scalar_one_or_none()
    if not job:
        return HTMLResponse("Not found", status_code=404)
    return request.app.state.templates.TemplateResponse(
        "components/crawl_progress.html",
        {
            "request": request,
            "chatbot_id": chatbot_id,
            "job_id": str(job.id),
            "status": job.status,
            "pages_discovered": job.pages_discovered,
            "pages_queued": job.pages_queued,
            "pages_failed": job.pages_failed,
            "error_message": job.error_message,
        },
    )
