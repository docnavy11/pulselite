"""Unit tests for app.services.workspace_service."""
import pytest
from fastapi import HTTPException
from app.services.workspace_service import create_workspace, list_workspaces, get_workspace


@pytest.mark.asyncio
async def test_create_workspace_returns_workspace(db, agent):
    ws = await create_workspace(db, name="Test Corp", slug="test-corp-unique-x1", agent_id=agent.id)
    assert ws.name == "Test Corp"
    assert ws.slug == "test-corp-unique-x1"


@pytest.mark.asyncio
async def test_create_workspace_creates_owner_membership(db, agent):
    from sqlalchemy import select
    from app.models.organizational import WorkspaceMembership
    ws = await create_workspace(db, name="MyCo", slug="myco-slug-x1", agent_id=agent.id)
    result = await db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == ws.id,
            WorkspaceMembership.agent_id == agent.id,
        )
    )
    membership = result.scalar_one_or_none()
    assert membership is not None
    assert membership.role == "owner"


@pytest.mark.asyncio
async def test_create_workspace_duplicate_slug_raises_409(db, agent):
    await create_workspace(db, name="First", slug="same-slug-x1", agent_id=agent.id)
    with pytest.raises(HTTPException) as exc_info:
        await create_workspace(db, name="Second", slug="same-slug-x1", agent_id=agent.id)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_list_workspaces_returns_agents_workspaces(db, agent, workspace):
    workspaces = await list_workspaces(db, agent_id=agent.id)
    ws_ids = [ws.id for ws in workspaces]
    assert workspace.id in ws_ids


@pytest.mark.asyncio
async def test_list_workspaces_excludes_other_agents_workspaces(db, agent, second_workspace, second_agent):
    workspaces = await list_workspaces(db, agent_id=agent.id)
    ws_ids = [ws.id for ws in workspaces]
    assert second_workspace.id not in ws_ids


@pytest.mark.asyncio
async def test_get_workspace_valid_member(db, agent, workspace):
    result = await get_workspace(db, workspace_id=workspace.id, agent_id=agent.id)
    assert result.id == workspace.id


@pytest.mark.asyncio
async def test_get_workspace_non_member_raises_404(db, second_agent, workspace):
    with pytest.raises(HTTPException) as exc_info:
        await get_workspace(db, workspace_id=workspace.id, agent_id=second_agent.id)
    assert exc_info.value.status_code == 404
