"""Tests for Task 3: chatbot_id filter on GET /sentiment-trends."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversations import Conversation
from app.models.intelligence import ConversationAnalysis
from tests.factories import make_chatbot


async def _make_conv_with_sentiment(
    db: AsyncSession,
    workspace,
    chatbot,
    *,
    sentiment_score: float = 0.5,
    days_ago: int = 5,
):
    conv = Conversation(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        chatbot_id=chatbot.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(conv)
    await db.flush()

    ca = ConversationAnalysis(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        conversation_id=conv.id,
        sentiment_score=sentiment_score,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(ca)
    await db.flush()
    return conv, ca


@pytest.mark.asyncio
class TestSentimentTrendsChatbotFilter:

    async def test_without_chatbot_id_returns_all(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot_a = await make_chatbot(db, workspace, name="Bot A")
        bot_b = await make_chatbot(db, workspace, name="Bot B")
        await _make_conv_with_sentiment(db, workspace, bot_a, sentiment_score=0.8)
        await _make_conv_with_sentiment(db, workspace, bot_b, sentiment_score=0.2)

        resp = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/sentiment-trends"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        total_count = sum(d["count"] for d in data)
        assert total_count == 2

    async def test_with_chatbot_id_filters(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot_a = await make_chatbot(db, workspace, name="Bot A")
        bot_b = await make_chatbot(db, workspace, name="Bot B")
        await _make_conv_with_sentiment(db, workspace, bot_a, sentiment_score=0.8)
        await _make_conv_with_sentiment(db, workspace, bot_b, sentiment_score=0.2)

        resp = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/sentiment-trends?chatbot_id={bot_a.id}"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        total_count = sum(d["count"] for d in data)
        assert total_count == 1

    async def test_chatbot_id_with_no_data_returns_empty(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot = await make_chatbot(db, workspace)
        fake_id = uuid.uuid4()

        resp = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/sentiment-trends?chatbot_id={fake_id}"
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_chatbot_filter_combined_with_days(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot = await make_chatbot(db, workspace)
        await _make_conv_with_sentiment(db, workspace, bot, days_ago=5)
        await _make_conv_with_sentiment(db, workspace, bot, days_ago=50)

        resp = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/sentiment-trends?chatbot_id={bot.id}&days=30"
        )
        assert resp.status_code == 200
        total_count = sum(d["count"] for d in resp.json()["data"])
        assert total_count == 1
