import uuid as _uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.services.plan_service import get_plan_limits
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


class WorkspaceSettingsUpdate(BaseModel):
    name: str | None = None
    timezone: str | None = None


class LLMSettingsResponse(BaseModel):
    openrouter_api_key_set: bool
    openrouter_base_url: str | None = None
    effective_base_url: str | None = None
    effective_api_key_set: bool = False
    allowed_models: list[str]
    internal_model: str | None = None


class LLMSettingsUpdate(BaseModel):
    openrouter_api_key: str | None = None
    openrouter_base_url: str | None = None
    allowed_models: list[str] = []
    internal_model: str | None = None


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


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace_settings(
    body: WorkspaceSettingsUpdate,
    workspace_id: _uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = result.scalar_one()
    if body.name is not None:
        ws.name = body.name.strip()
    if body.timezone is not None:
        ws.timezone = body.timezone
    await db.commit()
    await db.refresh(ws)
    return await workspace_service.get_workspace(db, workspace_id, current_user.id)


@router.get("/{workspace_id}/llm-settings", response_model=LLMSettingsResponse)
async def get_llm_settings(
    workspace_id: _uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return _build_llm_response(workspace)


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
    if body.openrouter_base_url is not None:
        workspace.openrouter_base_url = body.openrouter_base_url.strip() or None
    if len(body.allowed_models) > 100:
        raise HTTPException(status_code=400, detail="allowed_models may not exceed 100 items")
    workspace.allowed_models = body.allowed_models
    if body.internal_model is not None:
        workspace.internal_model = body.internal_model.strip() or None
    await db.commit()
    await db.refresh(workspace)
    return _build_llm_response(workspace)


def _build_llm_response(workspace: Workspace) -> LLMSettingsResponse:
    effective_base = workspace.openrouter_base_url or app_settings.AI_BASE_URL or None
    effective_key = bool(workspace.openrouter_api_key or app_settings.AI_API_KEY)
    return LLMSettingsResponse(
        openrouter_api_key_set=bool(workspace.openrouter_api_key),
        openrouter_base_url=workspace.openrouter_base_url,
        effective_base_url=effective_base,
        effective_api_key_set=effective_key,
        allowed_models=workspace.allowed_models or [],
        internal_model=workspace.internal_model,
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
    # Resolve API key: workspace override → AI_API_KEY env var
    api_key: str | None = None
    if workspace.openrouter_api_key:
        try:
            api_key = decrypt_api_key(workspace.openrouter_api_key)
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to decrypt API key")
    else:
        api_key = app_settings.AI_API_KEY

    if not api_key:
        raise HTTPException(status_code=400, detail="No API key configured")

    base_url = (workspace.openrouter_base_url or app_settings.AI_BASE_URL).rstrip("/")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{base_url}/models",
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

    _limits = get_plan_limits(workspace.plan)
    limit = _limits["chars_indexed"] if _limits["chars_indexed"] != -1 else None
    chars_remaining: int | None = None
    if limit is not None:
        chars_remaining = max(0, limit - workspace.chars_indexed)

    return WorkspaceUsageResponse(
        chars_indexed=workspace.chars_indexed,
        chars_limit=limit,
        chars_remaining=chars_remaining,
        plan=workspace.plan,
    )

