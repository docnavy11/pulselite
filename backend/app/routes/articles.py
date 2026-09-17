"""Article routes — CRUD + publish."""
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.knowledge import Article

router = APIRouter(prefix="/articles")


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def article_list(request: Request, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    articles = (await db.execute(
        select(Article).where(Article.workspace_id == workspace.id).order_by(Article.created_at.desc())
    )).scalars().all()
    return request.app.state.templates.TemplateResponse("articles/list.html", {
        "request": request, "articles": articles,
    })


@router.get("/new", response_class=HTMLResponse)
async def new_article(request: Request):
    return request.app.state.templates.TemplateResponse("articles/edit.html", {
        "request": request, "article": None,
    })


@router.post("")
async def create_article(
    request: Request, title: str = Form(...), body: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    article = Article(workspace_id=workspace.id, title=title, body=body, author_id=request.state.user.id)
    db.add(article)
    await db.flush()
    return RedirectResponse(f"/articles/{article.id}", status_code=303)


@router.get("/{article_id}", response_class=HTMLResponse)
async def article_detail(request: Request, article_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    article = (await db.execute(
        select(Article).where(Article.id == article_id, Article.workspace_id == workspace.id)
    )).scalar_one_or_none()
    if not article:
        return HTMLResponse("Not found", status_code=404)
    return request.app.state.templates.TemplateResponse("articles/edit.html", {
        "request": request, "article": article,
    })


@router.put("/{article_id}")
async def update_article(request: Request, article_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    article = (await db.execute(
        select(Article).where(Article.id == article_id, Article.workspace_id == workspace.id)
    )).scalar_one_or_none()
    if not article:
        return HTMLResponse("Not found", status_code=404)
    form = await request.form()
    if "title" in form:
        article.title = form["title"]
    if "body" in form:
        article.body = form["body"]
    await db.flush()
    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/toast.html", {
            "request": request, "message": "Article saved", "type": "success",
        })
    return RedirectResponse(f"/articles/{article_id}", status_code=303)


@router.post("/{article_id}/publish")
async def publish_article(request: Request, article_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    article = (await db.execute(
        select(Article).where(Article.id == article_id, Article.workspace_id == workspace.id)
    )).scalar_one_or_none()
    if not article:
        return HTMLResponse("Not found", status_code=404)
    article.state = "published"

    # Auto-assign to the first KB in the workspace if not already set
    if not article.knowledge_base_id:
        from app.models.knowledge import KnowledgeBase
        kb = (await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.workspace_id == workspace.id).limit(1)
        )).scalar_one_or_none()
        if kb:
            article.knowledge_base_id = kb.id

    await db.flush()

    if article.knowledge_base_id:
        from app.background.runner import submit_job
        await submit_job("reindex_article", {"article_id": str(article_id)})

    if request.headers.get("HX-Request"):
        return request.app.state.templates.TemplateResponse("components/toast.html", {
            "request": request, "message": "Article published", "type": "success",
        })
    return RedirectResponse(f"/articles/{article_id}", status_code=303)


@router.delete("/{article_id}")
async def delete_article(request: Request, article_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    workspace = request.state.workspace
    article = (await db.execute(
        select(Article).where(Article.id == article_id, Article.workspace_id == workspace.id)
    )).scalar_one_or_none()
    if article:
        await db.delete(article)
        await db.flush()
    return HTMLResponse("")
