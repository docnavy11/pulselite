import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.organizational import Agent
from app.schemas.knowledge_bases import KnowledgeBaseCreate, KnowledgeBaseResponse
from app.services import knowledge_base_service
from app.services.audit import log_audit

router = APIRouter(prefix="/workspaces/{workspace_id}/knowledge-bases", tags=["knowledge_bases"])


@router.post("", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    request: Request,
    body: KnowledgeBaseCreate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        kb = await knowledge_base_service.create_knowledge_base(db, workspace_id, **body.model_dump())
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid chatbot_id or constraint violation"
        )
    await log_audit(
        db,
        workspace_id,
        "knowledge_base.create",
        actor_id=current_user.id,
        actor_email=current_user.email,
        resource_type="knowledge_base",
        resource_id=str(kb.id),
        resource_name=kb.name,
        ip_address=request.client.host if request.client else None,
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
    request: Request,
    kb_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Fetch name before deletion for the audit record
    existing = await knowledge_base_service.get_knowledge_base(db, workspace_id, kb_id)
    kb_name = existing.name if existing else str(kb_id)
    await knowledge_base_service.delete_knowledge_base(db, workspace_id, kb_id)
    await log_audit(
        db,
        workspace_id,
        "knowledge_base.delete",
        actor_id=current_user.id,
        actor_email=current_user.email,
        resource_type="knowledge_base",
        resource_id=str(kb_id),
        resource_name=kb_name,
        ip_address=request.client.host if request.client else None,
    )
