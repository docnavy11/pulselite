import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_workspace
from app.models.actions import ChatbotAction
from app.models.knowledge import Chatbot
from app.schemas.actions import ActionCreate, ActionResponse, ActionUpdate
from app.services import action_service

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["actions"])


@router.post("/chatbots/{chatbot_id}/actions", response_model=ActionResponse)
async def create_action(
    chatbot_id: uuid.UUID,
    body: ActionCreate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    chatbot = (
        await db.execute(select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.workspace_id == workspace_id))
    ).scalar_one_or_none()
    if chatbot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chatbot not found")
    action = await action_service.create_action(db, workspace_id, chatbot_id, body.model_dump())
    await db.commit()
    return action


@router.get("/chatbots/{chatbot_id}/actions", response_model=list[ActionResponse])
async def list_actions(
    chatbot_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await action_service.list_actions(db, chatbot_id, enabled_only=False)


@router.patch("/chatbots/{chatbot_id}/actions/{action_id}", response_model=ActionResponse)
async def update_action(
    chatbot_id: uuid.UUID,
    action_id: uuid.UUID,
    body: ActionUpdate,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatbotAction).where(
            ChatbotAction.id == action_id,
            ChatbotAction.chatbot_id == chatbot_id,
            ChatbotAction.workspace_id == workspace_id,
        )
    )
    action = result.scalar_one_or_none()
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(action, k, v)
    await db.commit()
    return action


@router.delete("/chatbots/{chatbot_id}/actions/{action_id}", status_code=204)
async def delete_action(
    chatbot_id: uuid.UUID,
    action_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatbotAction).where(
            ChatbotAction.id == action_id,
            ChatbotAction.chatbot_id == chatbot_id,
            ChatbotAction.workspace_id == workspace_id,
        )
    )
    action = result.scalar_one_or_none()
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    await db.delete(action)
    await db.commit()
