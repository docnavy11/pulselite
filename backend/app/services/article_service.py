import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Article


async def create_article(db: AsyncSession, workspace_id: uuid.UUID, author_id: uuid.UUID, **kwargs) -> Article:
    article = Article(workspace_id=workspace_id, author_id=author_id, **kwargs)
    db.add(article)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid foreign key reference (knowledge_base_id or collection_id)",
        )
    await db.refresh(article)
    return article


async def list_articles(
    db: AsyncSession, workspace_id: uuid.UUID, knowledge_base_id: uuid.UUID | None = None
) -> list[Article]:
    query = select(Article).where(Article.workspace_id == workspace_id)
    if knowledge_base_id:
        query = query.where(Article.knowledge_base_id == knowledge_base_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_article(db: AsyncSession, workspace_id: uuid.UUID, article_id: uuid.UUID) -> Article:
    result = await db.execute(select(Article).where(Article.id == article_id, Article.workspace_id == workspace_id))
    article = result.scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return article


async def update_article(db: AsyncSession, workspace_id: uuid.UUID, article_id: uuid.UUID, **kwargs) -> Article:
    article = await get_article(db, workspace_id, article_id)
    for key, value in kwargs.items():
        if value is not None:
            setattr(article, key, value)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid foreign key reference (collection_id)"
        )
    await db.refresh(article)
    return article


async def publish_article(db: AsyncSession, workspace_id: uuid.UUID, article_id: uuid.UUID) -> Article:
    article = await get_article(db, workspace_id, article_id)
    article.state = "published"
    await db.flush()
    await db.refresh(article)
    return article


async def delete_article(db: AsyncSession, workspace_id: uuid.UUID, article_id: uuid.UUID) -> None:
    article = await get_article(db, workspace_id, article_id)
    await db.delete(article)
    await db.flush()
