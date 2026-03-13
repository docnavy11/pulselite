"""Tests for Task 4: recent_negative_feedback in dashboard response."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversations import Conversation, Message, MessageFeedback
from tests.factories import make_chatbot


async def _make_feedback(
    db: AsyncSession,
    workspace,
    chatbot,
    *,
    rating: str = "thumbs_down",
    comment: str | None = "Bad answer",
    days_ago: int = 5,
    message_content: str = "Bot response here",
):
    conv = Conversation(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        chatbot_id=chatbot.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(conv)
    await db.flush()

    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        workspace_id=workspace.id,
        content=message_content,
        author_type="bot",
        message_type="outgoing",
    )
    db.add(msg)
    await db.flush()

    fb = MessageFeedback(
        id=uuid.uuid4(),
        message_id=msg.id,
        conversation_id=conv.id,
        workspace_id=workspace.id,
        rating=rating,
        comment=comment,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(fb)
    await db.flush()
    return fb


@pytest.mark.asyncio
class TestRecentNegativeFeedback:

    async def test_key_present_in_response(self, auth_client: AsyncClient, workspace):
        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
        assert resp.status_code == 200
        assert "recent_negative_feedback" in resp.json()

    async def test_returns_thumbs_down_with_comments(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot = await make_chatbot(db, workspace)
        await _make_feedback(db, workspace, bot, comment="Terrible response")

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
        feedback = resp.json()["recent_negative_feedback"]
        assert len(feedback) == 1
        assert feedback[0]["comment"] == "Terrible response"

    async def test_excludes_thumbs_up(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot = await make_chatbot(db, workspace)
        await _make_feedback(db, workspace, bot, rating="thumbs_up", comment="Great!")

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
        assert resp.json()["recent_negative_feedback"] == []

    async def test_excludes_empty_comments(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot = await make_chatbot(db, workspace)
        await _make_feedback(db, workspace, bot, comment="")
        await _make_feedback(db, workspace, bot, comment=None)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
        assert resp.json()["recent_negative_feedback"] == []

    async def test_limits_to_3(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot = await make_chatbot(db, workspace)
        for i in range(5):
            await _make_feedback(db, workspace, bot, comment=f"Bad #{i}", days_ago=i + 1)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
        feedback = resp.json()["recent_negative_feedback"]
        assert len(feedback) == 3

    async def test_ordered_most_recent_first(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot = await make_chatbot(db, workspace)
        await _make_feedback(db, workspace, bot, comment="Old", days_ago=20)
        await _make_feedback(db, workspace, bot, comment="New", days_ago=1)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
        feedback = resp.json()["recent_negative_feedback"]
        assert feedback[0]["comment"] == "New"
        assert feedback[1]["comment"] == "Old"

    async def test_respects_days_window(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot = await make_chatbot(db, workspace)
        await _make_feedback(db, workspace, bot, comment="Recent", days_ago=5)
        await _make_feedback(db, workspace, bot, comment="Old", days_ago=50)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard?days=30")
        feedback = resp.json()["recent_negative_feedback"]
        assert len(feedback) == 1
        assert feedback[0]["comment"] == "Recent"

    async def test_includes_message_content(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot = await make_chatbot(db, workspace)
        await _make_feedback(
            db, workspace, bot,
            comment="Wrong answer",
            message_content="The sky is green.",
        )

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
        feedback = resp.json()["recent_negative_feedback"]
        assert feedback[0]["message_content"] == "The sky is green."

    async def test_response_item_shape(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot = await make_chatbot(db, workspace)
        await _make_feedback(db, workspace, bot, comment="Shape test")

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/dashboard")
        item = resp.json()["recent_negative_feedback"][0]
        assert "id" in item
        assert "comment" in item
        assert "created_at" in item
        assert "message_content" in item
