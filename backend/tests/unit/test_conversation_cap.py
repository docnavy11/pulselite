"""Tests for conversation cap enforcement."""
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.services.conversation_service import check_conversation_cap


@pytest.mark.asyncio
async def test_cap_skipped_in_self_hosted():
    with patch("app.services.conversation_service.is_cloud", return_value=False):
        # Should not raise regardless of count
        await check_conversation_cap(MagicMock(), MagicMock())


@pytest.mark.asyncio
async def test_cap_skipped_when_unlimited():
    workspace = MagicMock()
    workspace.plan = "enterprise"
    db = AsyncMock()

    with patch("app.services.conversation_service.is_cloud", return_value=True):
        with patch("app.services.conversation_service.get_plan_limits", return_value={"conversations": -1}):
            await check_conversation_cap(workspace, db)


@pytest.mark.asyncio
async def test_cap_enforced_when_limit_reached():
    from fastapi import HTTPException

    workspace = MagicMock()
    workspace.id = "test-id"
    workspace.plan = "free"
    db = AsyncMock()
    # Mock count query to return 100 (at limit)
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 100
    db.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.conversation_service.is_cloud", return_value=True):
        with patch("app.services.conversation_service.get_plan_limits", return_value={"conversations": 100}):
            with pytest.raises(HTTPException) as exc_info:
                await check_conversation_cap(workspace, db)
            assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_cap_allows_when_under_limit():
    workspace = MagicMock()
    workspace.id = "test-id"
    workspace.plan = "free"
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 50
    db.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.conversation_service.is_cloud", return_value=True):
        with patch("app.services.conversation_service.get_plan_limits", return_value={"conversations": 100}):
            await check_conversation_cap(workspace, db)  # Should not raise
