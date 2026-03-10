"""Unit tests for app.services.api_key_service."""
import uuid
import pytest
from fastapi import HTTPException
from app.services.api_key_service import (
    create_api_key,
    list_api_keys,
    revoke_api_key,
    validate_api_key,
)


@pytest.mark.asyncio
async def test_create_api_key_returns_key_string(db, workspace):
    api_key_record, full_key = await create_api_key(db, workspace_id=workspace.id, name="Test Key")
    assert full_key.startswith("pk_live_")
    assert len(full_key) > 20
    assert api_key_record.name == "Test Key"
    assert api_key_record.workspace_id == workspace.id


@pytest.mark.asyncio
async def test_create_api_key_does_not_store_plaintext(db, workspace):
    api_key_record, full_key = await create_api_key(db, workspace_id=workspace.id, name="Secure Key")
    assert api_key_record.key_hash != full_key


@pytest.mark.asyncio
async def test_validate_api_key_valid(db, workspace):
    _, full_key = await create_api_key(db, workspace_id=workspace.id, name="Valid Key")
    result = await validate_api_key(db, full_key)
    assert result.workspace_id == workspace.id


@pytest.mark.asyncio
async def test_validate_api_key_invalid_raises_401(db):
    with pytest.raises(HTTPException) as exc_info:
        await validate_api_key(db, "pk_live_totallyfakekey12345")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_revoke_api_key_makes_it_invalid(db, workspace):
    api_key_record, full_key = await create_api_key(db, workspace_id=workspace.id, name="To Revoke")
    await revoke_api_key(db, workspace_id=workspace.id, key_id=api_key_record.id)
    with pytest.raises(HTTPException) as exc_info:
        await validate_api_key(db, full_key)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_revoke_nonexistent_key_raises_404(db, workspace):
    with pytest.raises(HTTPException) as exc_info:
        await revoke_api_key(db, workspace_id=workspace.id, key_id=uuid.uuid4())
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_list_api_keys_returns_workspace_keys(db, workspace):
    await create_api_key(db, workspace_id=workspace.id, name="Key One")
    await create_api_key(db, workspace_id=workspace.id, name="Key Two")
    keys = await list_api_keys(db, workspace_id=workspace.id)
    assert len(keys) >= 2
    names = [k.name for k in keys]
    assert "Key One" in names
    assert "Key Two" in names
