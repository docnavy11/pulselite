import uuid as _uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PLAN_CHAR_LIMITS
from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.organizational import Agent, Workspace
from app.schemas.crawl import WorkspaceUsageResponse
from app.schemas.workspaces import WorkspaceCreate, WorkspaceResponse
from app.services import workspace_service
from app.services.encryption import decrypt_api_key, encrypt_api_key

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class DataRetentionResponse(BaseModel):
    data_retention_days: int | None


class DataRetentionUpdate(BaseModel):
    data_retention_days: int | None

    @field_validator("data_retention_days")
    @classmethod
    def validate_retention(cls, v: int | None) -> int | None:
        if v is not None and v < 30:
            raise ValueError("data_retention_days must be at least 30")
        if v is not None and v > 36500:  # 100 years max
            raise ValueError("data_retention_days must be at most 36500")
        return v


class LLMSettingsResponse(BaseModel):
    openrouter_api_key_set: bool
    allowed_models: list[str]


class LLMSettingsUpdate(BaseModel):
    openrouter_api_key: str | None = None
    allowed_models: list[str] = []


@router.post("", response_model=WorkspaceResponse)
async def create_workspace(
    body: WorkspaceCreate,
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await workspace_service.create_workspace(db, body.name, body.slug, current_user.id)
    return workspace


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await workspace_service.list_workspaces(db, current_user.id)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace_detail(
    workspace_id: str,
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        ws_uuid = _uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid workspace_id format")
    return await workspace_service.get_workspace(db, ws_uuid, current_user.id)


@router.get("/{workspace_id}/llm-settings", response_model=LLMSettingsResponse)
async def get_llm_settings(
    workspace_id: _uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return LLMSettingsResponse(
        openrouter_api_key_set=bool(workspace.openrouter_api_key),
        allowed_models=workspace.allowed_models or [],
    )


@router.put("/{workspace_id}/llm-settings", response_model=LLMSettingsResponse)
async def update_llm_settings(
    body: LLMSettingsUpdate,
    workspace_id: _uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    if body.openrouter_api_key is not None:
        if body.openrouter_api_key.strip() == "":
            workspace.openrouter_api_key = None
        else:
            workspace.openrouter_api_key = encrypt_api_key(body.openrouter_api_key)
    if len(body.allowed_models) > 100:
        raise HTTPException(status_code=400, detail="allowed_models may not exceed 100 items")
    workspace.allowed_models = body.allowed_models
    await db.commit()
    await db.refresh(workspace)
    return LLMSettingsResponse(
        openrouter_api_key_set=bool(workspace.openrouter_api_key),
        allowed_models=workspace.allowed_models or [],
    )


@router.get("/{workspace_id}/llm-settings/models")
async def list_openrouter_models(
    workspace_id: _uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    if not workspace.openrouter_api_key:
        raise HTTPException(status_code=400, detail="No OpenRouter API key configured for this workspace")
    try:
        api_key = decrypt_api_key(workspace.openrouter_api_key)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to decrypt OpenRouter API key")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch models from OpenRouter")

    data = resp.json()
    # Filter to text generation models only (exclude pure embedding/image models)
    models = [
        {
            "id": m["id"],
            "name": m.get("name", m["id"]),
            "context_length": m.get("context_length"),
            "pricing": m.get("pricing"),
        }
        for m in data.get("data", [])
        if "embedding" not in m["id"]
    ]
    return {"models": models}


@router.get("/{workspace_id}/data-retention", response_model=DataRetentionResponse)
async def get_data_retention(
    workspace_id: _uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return DataRetentionResponse(data_retention_days=workspace.data_retention_days)


@router.put("/{workspace_id}/data-retention", response_model=DataRetentionResponse)
async def update_data_retention(
    body: DataRetentionUpdate,
    workspace_id: _uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    workspace.data_retention_days = body.data_retention_days
    await db.commit()
    await db.refresh(workspace)
    return DataRetentionResponse(data_retention_days=workspace.data_retention_days)


@router.get("/{workspace_id}/usage", response_model=WorkspaceUsageResponse)
async def get_workspace_usage(
    workspace_id: _uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    limit = PLAN_CHAR_LIMITS.get(workspace.plan)
    chars_remaining: int | None = None
    if limit is not None:
        chars_remaining = max(0, limit - workspace.chars_indexed)

    return WorkspaceUsageResponse(
        chars_indexed=workspace.chars_indexed,
        chars_limit=limit,
        chars_remaining=chars_remaining,
        plan=workspace.plan,
    )

