import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.organizational import Agent
from app.schemas.api_keys import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse
from app.services import api_key_service
from app.services.audit import log_audit

router = APIRouter(prefix="/workspaces/{workspace_id}/api-keys", tags=["api_keys"])


@router.post("", response_model=ApiKeyCreatedResponse)
async def create_api_key(
    request: Request,
    body: ApiKeyCreate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    api_key, full_key = await api_key_service.create_api_key(db, workspace_id, body.name)
    await log_audit(
        db,
        workspace_id,
        "api_key.create",
        actor_id=current_user.id,
        actor_email=current_user.email,
        resource_type="api_key",
        resource_id=str(api_key.id),
        resource_name=api_key.name,
        ip_address=request.client.host if request.client else None,
    )
    return ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        full_key=full_key,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await api_key_service.list_api_keys(db, workspace_id)


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    request: Request,
    key_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await api_key_service.revoke_api_key(db, workspace_id, key_id)
    await log_audit(
        db,
        workspace_id,
        "api_key.revoke",
        actor_id=current_user.id,
        actor_email=current_user.email,
        resource_type="api_key",
        resource_id=str(key_id),
        ip_address=request.client.host if request.client else None,
    )
