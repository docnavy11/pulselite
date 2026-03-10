import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace
from app.schemas.knowledge_bases import KnowledgeBaseCreate, KnowledgeBaseResponse
from app.services import knowledge_base_service

router = APIRouter(prefix="/workspaces/{workspace_id}/knowledge-bases", tags=["knowledge_bases"])


@router.post("", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    try:
        kb = await knowledge_base_service.create_knowledge_base(db, workspace_id, **body.model_dump())
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid chatbot_id or constraint violation"
        )
    return kb


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    workspace_id: uuid.UUID = Depends(get_workspace),
    chatbot_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await knowledge_base_service.list_knowledge_bases(db, workspace_id, chatbot_id)


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await knowledge_base_service.get_knowledge_base(db, workspace_id, kb_id)


@router.delete("/{kb_id}", status_code=204)
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    await knowledge_base_service.delete_knowledge_base(db, workspace_id, kb_id)
