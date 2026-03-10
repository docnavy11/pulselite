# backend/tests/integration/test_autoconfig_api.py
"""Integration tests for POST /chatbots/{id}/autoconfig."""
import uuid
import pytest
from unittest.mock import AsyncMock, patch

from tests.factories import make_chatbot, make_knowledge_base, make_document
from app.services.autoconfig import AutoConfigResult


def _mock_autoconfig_result() -> AutoConfigResult:
    return AutoConfigResult(
        name="Test Bot",
        welcome_message="Hello!",
        system_prompt="You are helpful.",
        suggested_questions=["Q1?", "Q2?", "Q3?", "Q4?"],
        fallback_message="I don't know.",
        brand_color="#4F46E5",
    )


class TestAutoconfigEndpoint:

    async def test_autoconfig_updates_chatbot_fields(self, db, auth_client, workspace):
        from app.services.fetcher import FetchResult
        from app.models.knowledge import Chunk

        bot = await make_chatbot(db, workspace, name="Old Name")
        kb = await make_knowledge_base(db, workspace, bot)
        doc = await make_document(db, workspace, kb, raw_content="We help with product questions.")
        chunk = Chunk(
            workspace_id=workspace.id,
            document_id=doc.id,
            knowledge_base_id=kb.id,
            chunk_index=0,
            content="We help customers with product questions.",
        )
        db.add(chunk)
        await db.flush()

        with patch("app.services.autoconfig_service.generate", new_callable=AsyncMock) as mock_gen:
            with patch("app.services.autoconfig_service.fetch", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = FetchResult(
                    url="https://a.com", html="<html></html>", text="content",
                    title=None, theme_color=None, status_code=200, used_playwright=False,
                )
                mock_gen.return_value = _mock_autoconfig_result()

                r = await auth_client.post(
                    f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}/autoconfig",
                    json={"knowledge_base_id": str(kb.id)},
                )

        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Test Bot"
        assert data["welcome_message"] == "Hello!"
        assert data["brand_color"] == "#4F46E5"
        assert len(data["suggested_questions"]) == 4

    async def test_autoconfig_returns_422_for_empty_kb(self, db, auth_client, workspace):
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)

        r = await auth_client.post(
            f"/api/v1/workspaces/{workspace.id}/chatbots/{bot.id}/autoconfig",
            json={"knowledge_base_id": str(kb.id)},
        )
        assert r.status_code == 422
        assert "no indexed content" in r.json()["detail"].lower()

    async def test_autoconfig_returns_404_for_unknown_chatbot(self, auth_client, workspace):
        r = await auth_client.post(
            f"/api/v1/workspaces/{workspace.id}/chatbots/{uuid.uuid4()}/autoconfig",
            json={"knowledge_base_id": str(uuid.uuid4())},
        )
        assert r.status_code == 404

    async def test_autoconfig_tenant_isolation(self, auth_client, second_workspace):
        r = await auth_client.post(
            f"/api/v1/workspaces/{second_workspace.id}/chatbots/{uuid.uuid4()}/autoconfig",
            json={"knowledge_base_id": str(uuid.uuid4())},
        )
        assert r.status_code == 403
