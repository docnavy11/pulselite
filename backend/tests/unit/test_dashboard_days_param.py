"""Tests for Task 1: days query parameter on GET /dashboard."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversations import Conversation
from tests.factories import make_chatbot


async def _make_conv(db: AsyncSession, workspace, chatbot, *, days_ago: int = 0, resolved: bool = False):
    """Helper to create a conversation at a specific age."""
    conv = Conversation(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        chatbot_id=chatbot.id,
        autonomous_resolved=resolved,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(conv)
    await db.flush()
    return conv


@pytest.mark.asyncio
class TestDashboardDaysParam:

    async def test_default_days_is_30(self, auth_client: AsyncClient, db: AsyncSession, workspace):
        """Without ?days=, the endpoint should use a 30-day window."""
        bot = await make_chatbot(db, workspace)
        # conversation 25 days ago -> inside 30-day window
        await _make_conv(db, workspace, bot, days_ago=25, resolved=True)
        # conversation 35 days ago -> outside 30-day window
        await _make_conv(db, workspace, bot, days_ago=35, resolved=True)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["stats"]["total_conversations"] == 1

    async def test_days_7_narrows_window(self, auth_client: AsyncClient, db: AsyncSession, workspace):
        bot = await make_chatbot(db, workspace)
        await _make_conv(db, workspace, bot, days_ago=5)
        await _make_conv(db, workspace, bot, days_ago=10)  # outside 7-day window

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard?days=7")
        assert resp.status_code == 200
        assert resp.json()["stats"]["total_conversations"] == 1

    async def test_days_90_widens_window(self, auth_client: AsyncClient, db: AsyncSession, workspace):
        bot = await make_chatbot(db, workspace)
        await _make_conv(db, workspace, bot, days_ago=80)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard?days=90")
        assert resp.status_code == 200
        assert resp.json()["stats"]["total_conversations"] == 1

    async def test_days_validation_rejects_zero(self, auth_client: AsyncClient, workspace):
        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard?days=0")
        assert resp.status_code == 422

    async def test_days_validation_rejects_over_90(self, auth_client: AsyncClient, workspace):
        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard?days=91")
        assert resp.status_code == 422

    async def test_prev_period_uses_same_window_size(self, auth_client: AsyncClient, db: AsyncSession, workspace):
        """With days=10, prev period is days 10-20 ago."""
        bot = await make_chatbot(db, workspace)
        # Current period (0-10 days ago): 1 resolved out of 1
        await _make_conv(db, workspace, bot, days_ago=5, resolved=True)
        # Previous period (10-20 days ago): 0 resolved out of 1
        await _make_conv(db, workspace, bot, days_ago=15, resolved=False)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard?days=10")
        assert resp.status_code == 200
        body = resp.json()
        # current rate = 1.0, prev rate = 0.0, trend = 1.0
        assert body["resolution_rate"] == 1.0
        assert body["resolution_rate_trend"] == 1.0
