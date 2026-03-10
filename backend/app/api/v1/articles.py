import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.organizational import Agent
from app.schemas.articles import ArticleCreate, ArticleResponse, ArticleUpdate
from app.services import article_service

router = APIRouter(prefix="/workspaces/{workspace_id}/articles", tags=["articles"])


@router.post("", response_model=ArticleResponse)
async def create_article(
    body: ArticleCreate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await article_service.create_article(db, workspace_id, current_user.id, **body.model_dump())


@router.get("", response_model=list[ArticleResponse])
async def list_articles(
    workspace_id: uuid.UUID = Depends(get_workspace),
    knowledge_base_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await article_service.list_articles(db, workspace_id, knowledge_base_id)


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await article_service.get_article(db, workspace_id, article_id)


@router.put("/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: uuid.UUID,
    body: ArticleUpdate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await article_service.update_article(db, workspace_id, article_id, **body.model_dump(exclude_unset=True))


@router.put("/{article_id}/publish", response_model=ArticleResponse)
async def publish_article(
    article_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await article_service.publish_article(db, workspace_id, article_id)


@router.delete("/{article_id}", status_code=204)
async def delete_article(
    article_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    await article_service.delete_article(db, workspace_id, article_id)
