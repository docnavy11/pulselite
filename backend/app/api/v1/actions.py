import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace
from app.schemas.actions import ActionCreate, ActionResponse, ActionUpdate
from app.services import action_service

router = APIRouter(
    prefix="/workspaces/{workspace_id}/chatbots/{chatbot_id}/actions",
    tags=["actions"],
)


@router.get("", response_model=list[ActionResponse])
async def list_actions(
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await action_service.list_actions(db, workspace_id, chatbot_id)


@router.post("", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
async def create_action(
    chatbot_id: uuid.UUID,
    body: ActionCreate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await action_service.create_action(
        db,
        workspace_id=workspace_id,
        chatbot_id=chatbot_id,
        **body.model_dump(),
    )


@router.put("/{action_id}", response_model=ActionResponse)
async def update_action(
    chatbot_id: uuid.UUID,
    action_id: uuid.UUID,
    body: ActionUpdate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    updated = await action_service.update_action(
        db, action_id, workspace_id, body.model_dump(exclude_unset=True)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Action not found")
    return updated


@router.delete("/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action(
    chatbot_id: uuid.UUID,
    action_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    deleted = await action_service.delete_action(db, action_id, workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Action not found")
