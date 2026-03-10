# backend/tests/integration/test_crawl_api.py
"""Integration tests for POST /crawl and GET /crawl/{job_id}."""
import pytest
from unittest.mock import patch


class TestCrawlEndpoint:

    async def test_crawl_creates_kb_and_job(self, auth_client, workspace):
        """POST /crawl returns job_id and kb_id immediately (async — crawl runs in background)."""
        with patch("app.api.v1.crawl.crawl_website") as mock_task:
            mock_task.delay.return_value = None
            r = await auth_client.post(
                f"/api/v1/workspaces/{workspace.id}/crawl",
                json={"url": "https://a.com", "max_pages": 50},
            )

        assert r.status_code == 201
        data = r.json()
        assert "job_id" in data
        assert "kb_id" in data
        # Job starts with 0 — crawl runs asynchronously in Celery
        assert data["pages_discovered"] == 0
        assert data["pages_queued"] == 0

    async def test_crawl_job_is_persisted(self, db, auth_client, workspace):
        """After POST /crawl the CrawlJob row exists in the DB with status=pending."""
        from sqlalchemy import select
        from app.models.knowledge import CrawlJob

        with patch("app.api.v1.crawl.crawl_website") as mock_task:
            mock_task.delay.return_value = None
            r = await auth_client.post(
                f"/api/v1/workspaces/{workspace.id}/crawl",
                json={"url": "https://a.com", "max_pages": 10},
            )

        assert r.status_code == 201
        job_id = r.json()["job_id"]

        result = await db.execute(select(CrawlJob).where(CrawlJob.id == job_id))
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "pending"
        assert job.root_url == "https://a.com"

    async def test_crawl_kb_linked_to_chatbot(self, db, auth_client, workspace):
        """KB created by crawl is linked to the chatbot_id if provided."""
        from sqlalchemy import select
        from app.models.knowledge import KnowledgeBase
        from tests.factories import make_chatbot

        bot = await make_chatbot(db, workspace)

        with patch("app.api.v1.crawl.crawl_website") as mock_task:
            mock_task.delay.return_value = None
            r = await auth_client.post(
                f"/api/v1/workspaces/{workspace.id}/crawl",
                json={"url": "https://a.com", "max_pages": 5, "chatbot_id": str(bot.id)},
            )

        assert r.status_code == 201
        kb_id = r.json()["kb_id"]

        result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
        kb = result.scalar_one_or_none()
        assert kb is not None
        assert str(kb.chatbot_id) == str(bot.id)

    async def test_get_crawl_status(self, db, auth_client, workspace):
        """GET /crawl/{job_id} returns job status."""
        with patch("app.api.v1.crawl.crawl_website") as mock_task:
            mock_task.delay.return_value = None
            post_r = await auth_client.post(
                f"/api/v1/workspaces/{workspace.id}/crawl",
                json={"url": "https://a.com", "max_pages": 5},
            )
        job_id = post_r.json()["job_id"]

        r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/crawl/{job_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["job_id"] == job_id
        assert data["status"] == "pending"
        assert "docs_indexed" in data
        assert "docs_total" in data

    async def test_get_crawl_status_404_unknown_job(self, auth_client, workspace):
        import uuid
        r = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/crawl/{uuid.uuid4()}"
        )
        assert r.status_code == 404

    async def test_crawl_invalid_url_scheme(self, auth_client, workspace):
        r = await auth_client.post(
            f"/api/v1/workspaces/{workspace.id}/crawl",
            json={"url": "ftp://evil.com", "max_pages": 10},
        )
        assert r.status_code == 422

    async def test_crawl_max_pages_zero_rejected(self, auth_client, workspace):
        r = await auth_client.post(
            f"/api/v1/workspaces/{workspace.id}/crawl",
            json={"url": "https://a.com", "max_pages": 0},
        )
        assert r.status_code == 422
