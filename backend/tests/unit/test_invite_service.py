"""Unit tests for app.services.invite_service."""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy import select

from app.services.invite_service import (
    create_invite,
    accept_invite,
    list_invites,
    revoke_invite,
)


@pytest.mark.asyncio
async def test_create_invite_returns_invite(db, workspace, agent):
    """create_invite returns a WorkspaceInvite with expected fields."""
    invite = await create_invite(
        db,
        workspace_id=workspace.id,
        email="newmember@example.com",
        role="member",
        invited_by_id=agent.id,
    )
    assert invite.email == "newmember@example.com"
    assert invite.role == "member"
    assert invite.token is not None
    assert len(invite.token) > 20


@pytest.mark.asyncio
async def test_create_invite_has_expiry(db, workspace, agent):
    """Invite expires_at is set more than 6 days in the future."""
    invite = await create_invite(
        db,
        workspace_id=workspace.id,
        email="expires@example.com",
        role="member",
        invited_by_id=agent.id,
    )
    assert invite.expires_at is not None
    now = datetime.now(timezone.utc)
    expires = invite.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    assert expires > now + timedelta(days=6)


@pytest.mark.asyncio
async def test_accept_invite_creates_membership(db, workspace, agent):
    """accept_invite creates a new Agent and WorkspaceMembership with correct role."""
    invite = await create_invite(
        db,
        workspace_id=workspace.id,
        email="invitee@example.com",
        role="member",
        invited_by_id=agent.id,
    )
    from app.models.organizational import WorkspaceMembership

    new_agent = await accept_invite(
        db,
        token=invite.token,
        full_name="Invited User",
        password="SecurePass123!",
    )
    assert new_agent.email == "invitee@example.com"

    result = await db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.agent_id == new_agent.id,
            WorkspaceMembership.workspace_id == workspace.id,
        )
    )
    membership = result.scalar_one_or_none()
    assert membership is not None
    assert membership.role == "member"


@pytest.mark.asyncio
async def test_accept_invite_marks_accepted_at(db, workspace, agent):
    """accept_invite sets accepted_at on the invite record."""
    invite = await create_invite(
        db,
        workspace_id=workspace.id,
        email="markaccepted@example.com",
        role="member",
        invited_by_id=agent.id,
    )
    await accept_invite(
        db,
        token=invite.token,
        full_name="Mark Accepted",
        password="SecurePass123!",
    )
    assert invite.accepted_at is not None


@pytest.mark.asyncio
async def test_accept_invalid_token_raises_404(db):
    """Accepting a non-existent token raises HTTP 404."""
    with pytest.raises(HTTPException) as exc_info:
        await accept_invite(
            db,
            token="totallyfaketoken",
            full_name="Nobody",
            password="pass",
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_accept_already_accepted_invite_raises_404(db, workspace, agent):
    """Accepting an already-accepted invite raises HTTP 404."""
    invite = await create_invite(
        db,
        workspace_id=workspace.id,
        email="double@example.com",
        role="member",
        invited_by_id=agent.id,
    )
    await accept_invite(
        db, token=invite.token, full_name="First Accept", password="SecurePass123!"
    )
    # Second accept on the same token should fail
    with pytest.raises(HTTPException) as exc_info:
        await accept_invite(
            db, token=invite.token, full_name="Second Accept", password="SecurePass123!"
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_list_invites_returns_workspace_invites(db, workspace, agent):
    """list_invites returns all invites for the given workspace."""
    await create_invite(db, workspace.id, "a@test.com", "member", agent.id)
    await create_invite(db, workspace.id, "b@test.com", "admin", agent.id)
    invites = await list_invites(db, workspace.id)
    emails = [i.email for i in invites]
    assert "a@test.com" in emails
    assert "b@test.com" in emails


@pytest.mark.asyncio
async def test_list_invites_empty_for_new_workspace(db, workspace, agent):
    """list_invites returns an empty list when no invites exist."""
    # Use a fresh workspace that has no invites
    import uuid
    from app.models.organizational import Workspace

    fresh_ws = Workspace(
        id=uuid.uuid4(),
        name="Empty WS",
        slug=f"empty-ws-{uuid.uuid4().hex[:8]}",
        plan="pro",
    )
    db.add(fresh_ws)
    await db.flush()

    invites = await list_invites(db, fresh_ws.id)
    assert invites == []


@pytest.mark.asyncio
async def test_revoke_invite_prevents_acceptance(db, workspace, agent):
    """After revoke_invite, accepting the token raises HTTPException (record deleted)."""
    invite = await create_invite(
        db, workspace.id, "revoke@test.com", "member", agent.id
    )
    invite_id = invite.id
    token = invite.token
    await revoke_invite(db, workspace.id, invite_id)
    # After delete, the token no longer exists → accept raises 404
    with pytest.raises(HTTPException) as exc_info:
        await accept_invite(db, token=token, full_name="X", password="pass")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_revoke_invite_deletes_record(db, workspace, agent):
    """revoke_invite physically deletes the WorkspaceInvite row."""
    from app.models.invites import WorkspaceInvite

    invite = await create_invite(
        db, workspace.id, "deleted@test.com", "member", agent.id
    )
    invite_id = invite.id
    await revoke_invite(db, workspace.id, invite_id)

    result = await db.execute(
        select(WorkspaceInvite).where(WorkspaceInvite.id == invite_id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_revoke_nonexistent_invite_is_noop(db, workspace, agent):
    """revoke_invite on a non-existent ID silently does nothing (no exception)."""
    import uuid

    # Should not raise
    await revoke_invite(db, workspace.id, uuid.uuid4())
