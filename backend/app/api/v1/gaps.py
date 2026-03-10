import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.intelligence import GapCluster, GapEvent
from app.models.knowledge import Article
from app.models.organizational import Agent
from app.schemas.gaps import GapClusterArticleUpdate, GapClusterDetailResponse, GapClusterResponse
from app.workers.tasks.reindex_article import reindex_article

router = APIRouter(tags=["gaps"])


@router.get(
    "/workspaces/{workspace_id}/gap-clusters",
    response_model=list[GapClusterResponse],
)
async def list_gap_clusters(
    workspace_id: uuid.UUID = Depends(get_workspace),
    status_filter: str | None = None,
    chatbot_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    if status_filter and "\x00" in status_filter:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="status_filter must not contain null bytes"
        )
    query = select(GapCluster).where(GapCluster.workspace_id == workspace_id)
    if status_filter:
        query = query.where(GapCluster.status == status_filter)
    if chatbot_id:
        query = query.where(GapCluster.chatbot_id == chatbot_id)
    query = query.order_by(GapCluster.gap_count.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get(
    "/workspaces/{workspace_id}/gap-clusters/{cluster_id}",
    response_model=GapClusterDetailResponse,
)
async def get_gap_cluster(
    cluster_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(
        select(GapCluster).where(
            GapCluster.id == cluster_id,
            GapCluster.workspace_id == workspace_id,
        )
    )
    cluster = result.scalar_one_or_none()
    if cluster is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gap cluster not found")

    events_result = await db.execute(select(GapEvent.query).where(GapEvent.gap_cluster_id == cluster_id).limit(20))
    example_queries = [row[0] for row in events_result.all()]

    response_data = {
        "id": cluster.id,
        "workspace_id": cluster.workspace_id,
        "chatbot_id": cluster.chatbot_id,
        "topic_label": cluster.topic_label,
        "topic_keywords": cluster.topic_keywords,
        "gap_count": cluster.gap_count,
        "representative_query": cluster.representative_query,
        "status": cluster.status,
        "draft_article_id": cluster.draft_article_id,
        "resolved_at": cluster.resolved_at,
        "clustered_at": cluster.clustered_at,
        "created_at": cluster.created_at,
        "example_queries": example_queries,
    }

    if cluster.draft_article_id:
        article_result = await db.execute(select(Article).where(Article.id == cluster.draft_article_id))
        article = article_result.scalar_one_or_none()
        if article:
            response_data["draft_article_title"] = article.title
            response_data["draft_article_body"] = article.body

    return response_data


@router.post(
    "/workspaces/{workspace_id}/gap-clusters/{cluster_id}/approve",
    response_model=GapClusterResponse,
)
async def approve_gap_cluster(
    cluster_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(
        select(GapCluster).where(
            GapCluster.id == cluster_id,
            GapCluster.workspace_id == workspace_id,
        )
    )
    cluster = result.scalar_one_or_none()
    if cluster is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gap cluster not found")

    if not cluster.draft_article_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No draft article to approve")

    article_result = await db.execute(select(Article).where(Article.id == cluster.draft_article_id))
    article = article_result.scalar_one_or_none()
    if article:
        article.state = "published"
        article.approved_by = current_user.id
        article.approved_at = datetime.now(timezone.utc)

    cluster.status = "approved"
    cluster.resolved_at = datetime.now(timezone.utc)
    await db.commit()

    reindex_article.delay(str(cluster.draft_article_id))

    return cluster


@router.post(
    "/workspaces/{workspace_id}/gap-clusters/{cluster_id}/dismiss",
    response_model=GapClusterResponse,
)
async def dismiss_gap_cluster(
    cluster_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(
        select(GapCluster).where(
            GapCluster.id == cluster_id,
            GapCluster.workspace_id == workspace_id,
        )
    )
    cluster = result.scalar_one_or_none()
    if cluster is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gap cluster not found")

    cluster.status = "dismissed"
    cluster.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return cluster


@router.put(
    "/workspaces/{workspace_id}/gap-clusters/{cluster_id}/article",
    response_model=GapClusterDetailResponse,
)
async def update_draft_article(
    cluster_id: uuid.UUID,
    body: GapClusterArticleUpdate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(
        select(GapCluster).where(
            GapCluster.id == cluster_id,
            GapCluster.workspace_id == workspace_id,
        )
    )
    cluster = result.scalar_one_or_none()
    if cluster is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gap cluster not found")

    if not cluster.draft_article_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No draft article to edit")

    article_result = await db.execute(select(Article).where(Article.id == cluster.draft_article_id))
    article = article_result.scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft article not found")

    if body.title is not None:
        article.title = body.title
    if body.body is not None:
        article.body = body.body
    await db.commit()

    events_result = await db.execute(select(GapEvent.query).where(GapEvent.gap_cluster_id == cluster_id).limit(20))
    example_queries = [row[0] for row in events_result.all()]

    return {
        "id": cluster.id,
        "workspace_id": cluster.workspace_id,
        "chatbot_id": cluster.chatbot_id,
        "topic_label": cluster.topic_label,
        "topic_keywords": cluster.topic_keywords,
        "gap_count": cluster.gap_count,
        "representative_query": cluster.representative_query,
        "status": cluster.status,
        "draft_article_id": cluster.draft_article_id,
        "resolved_at": cluster.resolved_at,
        "clustered_at": cluster.clustered_at,
        "created_at": cluster.created_at,
        "example_queries": example_queries,
        "draft_article_title": article.title,
        "draft_article_body": article.body,
    }
