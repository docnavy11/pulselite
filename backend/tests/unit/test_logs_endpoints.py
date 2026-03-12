"""Unit tests for GET /logs/crawl-runs and GET /logs/documents."""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeBase
from tests.factories import make_chatbot, make_knowledge_base, make_document, make_crawl_job


class TestCrawlRunsLog:

    async def test_returns_empty_for_empty_workspace(self, auth_client: AsyncClient, workspace):
        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/logs/crawl-runs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    async def test_returns_jobs_for_workspace(self, auth_client: AsyncClient, db: AsyncSession, workspace):
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        job = await make_crawl_job(db, workspace, kb)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/logs/crawl-runs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["job_id"] == str(job.id)
        assert body["items"][0]["chatbot_name"] == bot.name

    async def test_workspace_isolation(self, auth_client: AsyncClient, db: AsyncSession, workspace, second_workspace):
        bot = await make_chatbot(db, second_workspace)
        kb = await make_knowledge_base(db, second_workspace, bot)
        await make_crawl_job(db, second_workspace, kb)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/logs/crawl-runs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_pagination_offset_beyond_total(self, auth_client: AsyncClient, db: AsyncSession, workspace):
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        await make_crawl_job(db, workspace, kb)

        resp = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/logs/crawl-runs?offset=999"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"] == []

    async def test_chatbot_name_null_when_kb_has_no_chatbot(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        kb = KnowledgeBase(
            id=uuid.uuid4(), workspace_id=workspace.id, name="Orphan KB"
        )
        db.add(kb)
        await db.flush()
        await make_crawl_job(db, workspace, kb)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/logs/crawl-runs")
        assert resp.status_code == 200
        assert resp.json()["items"][0]["chatbot_name"] is None


class TestDocumentsLog:

    async def test_returns_empty_for_empty_workspace(self, auth_client: AsyncClient, workspace):
        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/logs/documents")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    async def test_returns_documents_for_workspace(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        doc = await make_document(db, workspace, kb, title="My Page", status="indexed")

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/logs/documents")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["id"] == str(doc.id)
        assert item["knowledge_base_name"] == kb.name
        assert item["chatbot_name"] == bot.name

    async def test_workspace_isolation(
        self, auth_client: AsyncClient, db: AsyncSession, workspace, second_workspace
    ):
        bot = await make_chatbot(db, second_workspace)
        kb = await make_knowledge_base(db, second_workspace, bot)
        await make_document(db, second_workspace, kb)

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/logs/documents")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_ingestion_steps_included_in_response(
        self, auth_client: AsyncClient, db: AsyncSession, workspace
    ):
        from app.models.knowledge import Document
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        steps = [{"step": "extract", "status": "ok", "duration_ms": 100, "detail": "500 chars", "error": None}]
        doc = Document(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            knowledge_base_id=kb.id,
            title="Instrumented",
            source_type="text",
            raw_content="hello",
            status="indexed",
            ingestion_steps=steps,
            error_message=None,
        )
        db.add(doc)
        await db.flush()

        resp = await auth_client.get(f"/api/v1/workspaces/{workspace.id}/logs/documents")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["ingestion_steps"] == steps
