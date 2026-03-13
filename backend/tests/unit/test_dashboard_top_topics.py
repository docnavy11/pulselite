"""Tests for Task 2: per-topic resolution rate in top_topics."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversations import Conversation
from app.models.intelligence import ConversationAnalysis
from tests.factories import make_chatbot


async def _make_conv_with_analysis(
    db: AsyncSession,
    workspace,
    chatbot,
    *,
    topics: list[str],
    resolved: bool = False,
    days_ago: int = 5,
):
    conv = Conversation(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        chatbot_id=chatbot.id,
        autonomous_resolved=resolved,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(conv)
    await db.flush()

    ca = ConversationAnalysis(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        conversation_id=conv.id,
        topics=topics,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(ca)
    await db.flush()
    return conv


@pytest.mark.asyncio
class TestTopTopicsResolutionRate:

    async def test_returns_total_and_resolved_counts(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot = await make_chatbot(db, workspace)
        # 2 resolved conversations with "billing" topic
        await _make_conv_with_analysis(db, workspace, bot, topics=["billing"], resolved=True)
        await _make_conv_with_analysis(db, workspace, bot, topics=["billing"], resolved=True)
        # 1 unresolved conversation with "billing" topic
        await _make_conv_with_analysis(db, workspace, bot, topics=["billing"], resolved=False)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
        assert resp.status_code == 200
        topics = resp.json()["top_topics"]
        assert len(topics) == 1
        billing = topics[0]
        assert billing["topic"] == "billing"
        assert billing["total_count"] == 3
        assert billing["resolved_count"] == 2
        assert billing["resolution_rate"] == round(2 / 3, 4)

    async def test_includes_unresolved_only_topics(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        """Topics with zero resolved conversations should still appear."""
        bot = await make_chatbot(db, workspace)
        await _make_conv_with_analysis(db, workspace, bot, topics=["shipping"], resolved=False)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
        assert resp.status_code == 200
        topics = resp.json()["top_topics"]
        assert len(topics) == 1
        assert topics[0]["topic"] == "shipping"
        assert topics[0]["total_count"] == 1
        assert topics[0]["resolved_count"] == 0
        assert topics[0]["resolution_rate"] == 0.0

    async def test_response_shape_has_new_fields(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot = await make_chatbot(db, workspace)
        await _make_conv_with_analysis(db, workspace, bot, topics=["returns"], resolved=True)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
        topic = resp.json()["top_topics"][0]
        assert "total_count" in topic
        assert "resolved_count" in topic
        assert "resolution_rate" in topic
        # Old "count" field should no longer be present
        assert "count" not in topic

    async def test_topics_ordered_by_total_count_desc(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot = await make_chatbot(db, workspace)
        # "billing" appears 3 times
        for _ in range(3):
            await _make_conv_with_analysis(db, workspace, bot, topics=["billing"], resolved=True)
        # "shipping" appears 1 time
        await _make_conv_with_analysis(db, workspace, bot, topics=["shipping"], resolved=False)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
        topics = resp.json()["top_topics"]
        assert topics[0]["topic"] == "billing"
        assert topics[1]["topic"] == "shipping"
