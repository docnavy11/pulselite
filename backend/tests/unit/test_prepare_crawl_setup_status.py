"""Tests that prepare_crawl sets setup_status and active_crawl_job_id."""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestPrepareCrawlSetsSetupStatus:
    @pytest.mark.asyncio
    async def test_sets_crawling_when_chatbot_id_given(self):
        """When chatbot_id is provided, setup_status becomes 'crawling'."""
        # Pure logic test: verify the service sets the fields by inspecting
        # what get executed on the DB mock.
        from app.services.crawl_service import prepare_crawl

        chatbot_mock = MagicMock()
        chatbot_mock.setup_status = None
        chatbot_mock.active_crawl_job_id = None

        kb_mock = MagicMock()
        kb_mock.id = uuid.uuid4()

        job_mock = MagicMock()
        job_mock.id = uuid.uuid4()

        db = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        # execute returns the chatbot when querying for it
        chatbot_id = uuid.uuid4()
        workspace_id = uuid.uuid4()

        execute_result = AsyncMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=chatbot_mock)
        db.execute = AsyncMock(return_value=execute_result)

        with patch("app.services.crawl_service.KnowledgeBase", return_value=kb_mock), \
             patch("app.services.crawl_service.CrawlJob", return_value=job_mock):
            await prepare_crawl(db, workspace_id, "https://example.com", chatbot_id=chatbot_id)

        assert chatbot_mock.setup_status == "crawling"
        assert chatbot_mock.active_crawl_job_id == job_mock.id

    @pytest.mark.asyncio
    async def test_skips_update_when_no_chatbot_id(self):
        """When chatbot_id is None, setup_status is not touched."""
        from app.services.crawl_service import prepare_crawl

        kb_mock = MagicMock()
        kb_mock.id = uuid.uuid4()

        job_mock = MagicMock()
        job_mock.id = uuid.uuid4()

        db = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock()

        workspace_id = uuid.uuid4()

        with patch("app.services.crawl_service.KnowledgeBase", return_value=kb_mock), \
             patch("app.services.crawl_service.CrawlJob", return_value=job_mock):
            await prepare_crawl(db, workspace_id, "https://example.com")

        # db.execute should not have been called (no chatbot lookup needed)
        db.execute.assert_not_called()
