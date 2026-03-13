"""Tests for real-time event emissions in crawl_service."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_emit_to_workspace_imported_in_crawl_service():
    """Verify the crawl service imports the emit helper."""
    from app.services import crawl_service

    assert hasattr(crawl_service, "emit_to_workspace")


@pytest.mark.asyncio
async def test_prepare_crawl_emits_chatbot_status(db, workspace):
    """prepare_crawl should emit chatbot:status_changed when chatbot_id is provided."""
    from app.models.knowledge import Chatbot
    from app.services.crawl_service import prepare_crawl

    chatbot = Chatbot(workspace_id=workspace.id, name="test-bot")
    db.add(chatbot)
    await db.flush()

    with patch(
        "app.services.crawl_service.emit_to_workspace", new_callable=AsyncMock
    ) as mock_emit:
        await prepare_crawl(
            db,
            workspace_id=workspace.id,
            url="https://example.com",
            chatbot_id=chatbot.id,
        )
        # Should have emitted chatbot:status_changed with "crawling"
        mock_emit.assert_any_call(
            str(workspace.id),
            "chatbot:status_changed",
            {"chatbot_id": str(chatbot.id), "setup_status": "crawling"},
        )


@pytest.mark.asyncio
async def test_prepare_crawl_no_emit_without_chatbot_id(db, workspace):
    """prepare_crawl should NOT emit when chatbot_id is None."""
    from app.services.crawl_service import prepare_crawl

    with patch(
        "app.services.crawl_service.emit_to_workspace", new_callable=AsyncMock
    ) as mock_emit:
        await prepare_crawl(
            db,
            workspace_id=workspace.id,
            url="https://example.com",
            chatbot_id=None,
        )
        mock_emit.assert_not_called()
