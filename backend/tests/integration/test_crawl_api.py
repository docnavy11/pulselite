# backend/tests/integration/test_crawl_api.py
"""Integration tests for POST /crawl and GET /crawl/{job_id}."""
import pytest
from unittest.mock import patch

from app.services.crawler import CrawlResult
from app.services.fetcher import FetchResult


def _make_fetch(text: str = "content " * 100) -> FetchResult:
    return FetchResult(url="https://a.com/page", html="<html></html>",
                       text=text, title="Page", theme_color=None,
                       status_code=200, used_playwright=False)


class TestCrawlEndpoint:

    async def test_crawl_creates_kb_and_job(self, auth_client, workspace):
        """POST /crawl creates a KnowledgeBase and CrawlJob, returns job_id."""
        mock_crawl = CrawlResult(
            urls=["https://a.com/", "https://a.com/about"],
            total_discovered=2,
            over_limit=False,
            used_sitemap=False,
        )
        with patch("app.services.crawl_service.discover_urls", return_value=mock_crawl):
            with patch("app.services.crawl_service.fetch", return_value=_make_fetch()):
                with patch("app.workers.tasks.ingest_document.ingest_document.delay"):
                    r = await auth_client.post(
                        f"/api/v1/workspaces/{workspace.id}/crawl",
                        json={"url": "https://a.com", "max_pages": 50},
                    )

        assert r.status_code == 201
        data = r.json()
        assert "job_id" in data
        assert "kb_id" in data
        assert data["pages_discovered"] == 2
        assert data["pages_queued"] == 2
        assert data["over_limit"] is False

    async def test_crawl_reports_over_limit(self, auth_client, workspace):
        mock_crawl = CrawlResult(
            urls=["https://a.com/p1", "https://a.com/p2"],
            total_discovered=10,
            over_limit=True,
            used_sitemap=True,
        )
        with patch("app.services.crawl_service.discover_urls", return_value=mock_crawl):
            with patch("app.services.crawl_service.fetch", return_value=_make_fetch()):
                with patch("app.workers.tasks.ingest_document.ingest_document.delay"):
                    r = await auth_client.post(
                        f"/api/v1/workspaces/{workspace.id}/crawl",
                        json={"url": "https://a.com", "max_pages": 2},
                    )

        assert r.status_code == 201
        data = r.json()
        assert data["over_limit"] is True
        assert data["pages_discovered"] == 10
        assert data["limit"] == 2

    async def test_crawl_documents_use_source_type_text(self, db, auth_client, workspace):
        """Crawled Documents must have source_type='text' (not 'url') to avoid re-fetch."""
        from sqlalchemy import select
        from app.models.knowledge import Document

        mock_crawl = CrawlResult(
            urls=["https://a.com/"],
            total_discovered=1,
            over_limit=False,
            used_sitemap=False,
        )
        with patch("app.services.crawl_service.discover_urls", return_value=mock_crawl):
            with patch("app.services.crawl_service.fetch", return_value=_make_fetch()):
                with patch("app.workers.tasks.ingest_document.ingest_document.delay"):
                    r = await auth_client.post(
                        f"/api/v1/workspaces/{workspace.id}/crawl",
                        json={"url": "https://a.com", "max_pages": 5},
                    )

        assert r.status_code == 201
        result = await db.execute(
            select(Document).where(Document.workspace_id == workspace.id)
        )
        docs = result.scalars().all()
        assert len(docs) == 1
        assert docs[0].source_type == "text"
        assert docs[0].raw_content is not None

    async def test_get_crawl_status(self, auth_client, workspace):
        """GET /crawl/{job_id} returns job status."""
        mock_crawl = CrawlResult(
            urls=["https://a.com/"],
            total_discovered=1,
            over_limit=False,
            used_sitemap=False,
        )
        with patch("app.services.crawl_service.discover_urls", return_value=mock_crawl):
            with patch("app.services.crawl_service.fetch", return_value=_make_fetch()):
                with patch("app.workers.tasks.ingest_document.ingest_document.delay"):
                    post_r = await auth_client.post(
                        f"/api/v1/workspaces/{workspace.id}/crawl",
                        json={"url": "https://a.com", "max_pages": 5},
                    )
        job_id = post_r.json()["job_id"]

        r = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/crawl/{job_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["job_id"] == job_id
        assert data["status"] in ("pending", "running", "completed")

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
