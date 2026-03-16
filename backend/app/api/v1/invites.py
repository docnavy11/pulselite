import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_workspace
from app.models.organizational import Agent, WorkspaceMembership
from app.schemas.invites import InviteAccept, InviteCreate, InviteResponse
from app.services import invite_service
from app.services.audit_service import record_audit_event
from app.services.integrations.email import send_invite_email

router = APIRouter(tags=["invites"])


async def _require_admin(
    workspace_id: uuid.UUID,
    current_user: Agent,
    db: AsyncSession,
) -> None:
    result = await db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.agent_id == current_user.id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


@router.post("/workspaces/{workspace_id}/invites", response_model=InviteResponse)
async def create_invite(
    body: InviteCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(workspace_id, current_user, db)
    invite = await invite_service.create_invite(db, workspace_id, body.email, body.role, current_user.id)

    await record_audit_event(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        user_email=current_user.email,
        action="member.invited",
        resource_type="invite",
        resource_id=invite.id,
        ip_address=request.client.host if request.client else None,
        details={"invited_email": body.email, "role": body.role},
    )

    await db.commit()
    background_tasks.add_task(send_invite_email, invite.email, invite.token, workspace_id)
    return invite


@router.get("/workspaces/{workspace_id}/invites", response_model=list[InviteResponse])
async def list_invites(
    workspace_id: uuid.UUID = Depends(get_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await invite_service.list_invites(db, workspace_id)


@router.delete("/workspaces/{workspace_id}/invites/{invite_id}", status_code=204)
async def revoke_invite(
    invite_id: uuid.UUID,
    request: Request,
    workspace_id: uuid.UUID = Depends(get_workspace),
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(workspace_id, current_user, db)
    await invite_service.revoke_invite(db, workspace_id, invite_id)

    await record_audit_event(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        user_email=current_user.email,
        action="member.removed",
        resource_type="invite",
        resource_id=invite_id,
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()


@router.post("/invites/accept")
async def accept_invite(
    body: InviteAccept,
    db: AsyncSession = Depends(get_db),
):
    agent = await invite_service.accept_invite(db, body.token, body.full_name, body.password)
    await db.commit()
    return {"status": "ok", "email": agent.email}
