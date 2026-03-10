import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.organizational import Agent, Workspace

router = APIRouter(prefix="/workspaces/{workspace_id}/onboarding", tags=["onboarding"])

ONBOARDING_STEPS = {
    1: "Create workspace",
    2: "Create first chatbot",
    3: "Add knowledge base",
    4: "Upload documents",
    5: "Configure widget",
    6: "Test chat",
}


@router.get("")
async def get_onboarding(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one()

    return {
        "current_step": workspace.onboarding_step,
        "completed": workspace.onboarding_completed,
        "total_steps": len(ONBOARDING_STEPS),
        "steps": ONBOARDING_STEPS,
    }


@router.put("/step/{step_number}")
async def complete_step(
    step_number: int,
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    if step_number not in ONBOARDING_STEPS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid step number")

    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one()

    if step_number >= workspace.onboarding_step:
        workspace.onboarding_step = step_number + 1

    if workspace.onboarding_step > len(ONBOARDING_STEPS):
        workspace.onboarding_completed = True

    await db.commit()
    return {
        "current_step": workspace.onboarding_step,
        "completed": workspace.onboarding_completed,
    }


@router.post("/complete")
async def complete_onboarding(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
    current_user: Agent = Depends(get_current_user),
):
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one()

    workspace.onboarding_completed = True
    workspace.onboarding_step = len(ONBOARDING_STEPS) + 1
    await db.commit()

    return {"status": "ok", "completed": True}
