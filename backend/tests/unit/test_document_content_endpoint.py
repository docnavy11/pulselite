"""Tests for GET /documents/{id}/content endpoint."""
import uuid

import pytest
from httpx import AsyncClient

from tests.factories.chatbot import make_chatbot, make_knowledge_base, make_document
from app.models.knowledge import Chunk


class TestDocumentContentEndpoint:
    """GET /workspaces/{ws}/documents/{doc_id}/content"""

    @pytest.mark.asyncio
    async def test_returns_document_with_chunks_ordered(self, auth_client: AsyncClient, db, workspace):
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        doc = await make_document(db, workspace, kb, source_type="url", raw_content="Hello world")

        # Create chunks out of order to verify ordering
        c2 = Chunk(
            id=uuid.uuid4(),
            workspace_id=workspace.id, document_id=doc.id,
            knowledge_base_id=kb.id, chunk_index=1, content="Second chunk",
            heading_path="Section B", token_count=50,
        )
        c1 = Chunk(
            id=uuid.uuid4(),
            workspace_id=workspace.id, document_id=doc.id,
            knowledge_base_id=kb.id, chunk_index=0, content="First chunk",
            heading_path="Section A", token_count=40,
        )
        db.add_all([c2, c1])
        await db.flush()

        resp = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/documents/{doc.id}/content"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(doc.id)
        assert data["raw_content"] == "Hello world"
        assert len(data["chunks"]) == 2
        assert data["chunks"][0]["chunk_index"] == 0
        assert data["chunks"][0]["content"] == "First chunk"
        assert data["chunks"][1]["chunk_index"] == 1

    @pytest.mark.asyncio
    async def test_404_for_wrong_workspace(self, auth_client: AsyncClient, db, workspace, second_workspace):
        bot = await make_chatbot(db, second_workspace)
        kb = await make_knowledge_base(db, second_workspace, bot)
        doc = await make_document(db, second_workspace, kb, source_type="text")

        resp = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/documents/{doc.id}/content"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_empty_chunks_for_pending_document(self, auth_client: AsyncClient, db, workspace):
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        doc = await make_document(db, workspace, kb, source_type="url")

        resp = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/documents/{doc.id}/content"
        )
        assert resp.status_code == 200
        assert resp.json()["chunks"] == []

    @pytest.mark.asyncio
    async def test_null_raw_content(self, auth_client: AsyncClient, db, workspace):
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        doc = await make_document(db, workspace, kb, source_type="url", raw_content=None)

        resp = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/documents/{doc.id}/content"
        )
        assert resp.status_code == 200
        assert resp.json()["raw_content"] is None

    @pytest.mark.asyncio
    async def test_error_message_for_failed_document(self, auth_client: AsyncClient, db, workspace):
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        doc = await make_document(db, workspace, kb, source_type="url")
        doc.status = "failed"
        doc.error_message = "HTTP 403 Forbidden"
        await db.flush()

        resp = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/documents/{doc.id}/content"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "HTTP 403 Forbidden"

    @pytest.mark.asyncio
    async def test_chunk_has_id_field(self, auth_client: AsyncClient, db, workspace):
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        doc = await make_document(db, workspace, kb, source_type="text", raw_content="test")
        chunk = Chunk(
            id=uuid.uuid4(),
            workspace_id=workspace.id, document_id=doc.id,
            knowledge_base_id=kb.id, chunk_index=0, content="chunk",
            token_count=10,
        )
        db.add(chunk)
        await db.flush()

        resp = await auth_client.get(
            f"/api/v1/workspaces/{workspace.id}/documents/{doc.id}/content"
        )
        assert resp.status_code == 200
        assert "id" in resp.json()["chunks"][0]
        assert resp.json()["chunks"][0]["id"] == str(chunk.id)
