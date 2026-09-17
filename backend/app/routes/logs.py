"""Log viewing routes — tabbed interface matching React app."""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.knowledge import CrawlJob, Document
from app.models.task_log import BackgroundTaskLog

router = APIRouter(prefix="/logs")

PAGE_SIZE = 50


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def logs_page(
    request: Request,
    tab: str = Query("crawls"),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    workspace = request.state.workspace
    offset = (page - 1) * PAGE_SIZE

    crawl_jobs = []
    recent_docs = []
    tasks = []
    total = 0

    if tab == "crawls":
        total = (
            await db.execute(select(func.count(CrawlJob.id)).where(CrawlJob.workspace_id == workspace.id))
        ).scalar_one()
        crawl_jobs = (
            (
                await db.execute(
                    select(CrawlJob)
                    .where(CrawlJob.workspace_id == workspace.id)
                    .order_by(CrawlJob.created_at.desc())
                    .offset(offset)
                    .limit(PAGE_SIZE)
                )
            )
            .scalars()
            .all()
        )
    elif tab == "documents":
        total = (
            await db.execute(select(func.count(Document.id)).where(Document.workspace_id == workspace.id))
        ).scalar_one()
        recent_docs = (
            (
                await db.execute(
                    select(Document)
                    .where(Document.workspace_id == workspace.id)
                    .order_by(Document.updated_at.desc())
                    .offset(offset)
                    .limit(PAGE_SIZE)
                )
            )
            .scalars()
            .all()
        )
    elif tab == "tasks":
        total = (
            await db.execute(
                select(func.count(BackgroundTaskLog.id)).where(BackgroundTaskLog.workspace_id == workspace.id)
            )
        ).scalar_one()
        tasks = (
            (
                await db.execute(
                    select(BackgroundTaskLog)
                    .where(BackgroundTaskLog.workspace_id == workspace.id)
                    .order_by(BackgroundTaskLog.created_at.desc())
                    .offset(offset)
                    .limit(PAGE_SIZE)
                )
            )
            .scalars()
            .all()
        )

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    return request.app.state.templates.TemplateResponse(
        "logs/index.html",
        {
            "request": request,
            "crawl_jobs": crawl_jobs,
            "recent_docs": recent_docs,
            "tasks": tasks,
            "tab": tab,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )
