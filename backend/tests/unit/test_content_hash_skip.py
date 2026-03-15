"""Tests for content hash skip during re-ingestion."""
import hashlib
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy import select

from tests.factories.chatbot import make_chatbot, make_knowledge_base, make_document
from app.models.knowledge import Chunk, Document
from app.services.ingestion.pipeline import run_ingestion


class TestContentHashSkip:
    """Verify hash-based skip logic in the ingestion pipeline."""

    @pytest.mark.asyncio
    async def test_unchanged_content_skips_reingestion(self, db, workspace):
        """When content_hash matches, skip chunking/embedding, update last_indexed_at."""
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        content = "Hello world content"
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        doc = await make_document(
            db, workspace, kb,
            source_type="text", raw_content=content, status="stale",
        )
        doc.content_hash = content_hash
        doc.last_indexed_at = None
        await db.flush()

        with patch("app.services.ingestion.pipeline.embed_chunks", new_callable=AsyncMock) as mock_embed:
            await run_ingestion(db, doc.id)
            mock_embed.assert_not_called()

        await db.refresh(doc)
        assert doc.status == "indexed"
        assert doc.last_indexed_at is not None
        assert doc.content_hash == content_hash

        # Verify no new chunks were created
        result = await db.execute(select(Chunk).where(Chunk.document_id == doc.id))
        assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_unchanged_content_records_hash_check_step(self, db, workspace):
        """The ingestion_steps should contain a hash_check entry when skipped."""
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        content = "Some content"
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        doc = await make_document(
            db, workspace, kb,
            source_type="text", raw_content=content, status="stale",
        )
        doc.content_hash = content_hash
        await db.flush()

        await run_ingestion(db, doc.id)

        await db.refresh(doc)
        step_names = [s["step"] for s in (doc.ingestion_steps or [])]
        assert "hash_check" in step_names
        hash_step = next(s for s in doc.ingestion_steps if s["step"] == "hash_check")
        assert hash_step["status"] == "skipped"
        assert hash_step["detail"] == "content unchanged"

    @pytest.mark.asyncio
    async def test_changed_content_triggers_full_reingestion(self, db, workspace):
        """When content_hash differs, run full pipeline and store new hash."""
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        old_content = "Old content"
        new_content = "New content that is different"
        old_hash = hashlib.sha256(old_content.encode()).hexdigest()
        new_hash = hashlib.sha256(new_content.encode()).hexdigest()
        doc = await make_document(
            db, workspace, kb,
            source_type="text", raw_content=new_content, status="stale",
        )
        doc.content_hash = old_hash
        await db.flush()

        mock_embeddings = [[0.1] * 384]
        with patch("app.services.ingestion.pipeline.embed_chunks", new_callable=AsyncMock, return_value=mock_embeddings):
            await run_ingestion(db, doc.id)

        await db.refresh(doc)
        assert doc.status == "indexed"
        assert doc.content_hash == new_hash

        # Chunks should have been created
        result = await db.execute(select(Chunk).where(Chunk.document_id == doc.id))
        assert len(result.scalars().all()) > 0

    @pytest.mark.asyncio
    async def test_first_ingestion_stores_hash(self, db, workspace):
        """First ingestion (content_hash is NULL) should store the hash."""
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        content = "Brand new document"
        expected_hash = hashlib.sha256(content.encode()).hexdigest()
        doc = await make_document(
            db, workspace, kb,
            source_type="text", raw_content=content, status="pending",
        )
        assert doc.content_hash is None

        mock_embeddings = [[0.1] * 384]
        with patch("app.services.ingestion.pipeline.embed_chunks", new_callable=AsyncMock, return_value=mock_embeddings):
            await run_ingestion(db, doc.id)

        await db.refresh(doc)
        assert doc.content_hash == expected_hash
        assert doc.status == "indexed"

    @pytest.mark.asyncio
    async def test_first_ingestion_records_hash_check_ok(self, db, workspace):
        """First ingestion should record hash_check as 'ok' with 'first ingestion' detail."""
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        doc = await make_document(
            db, workspace, kb,
            source_type="text", raw_content="Some text", status="pending",
        )

        mock_embeddings = [[0.1] * 384]
        with patch("app.services.ingestion.pipeline.embed_chunks", new_callable=AsyncMock, return_value=mock_embeddings):
            await run_ingestion(db, doc.id)

        await db.refresh(doc)
        hash_step = next(s for s in doc.ingestion_steps if s["step"] == "hash_check")
        assert hash_step["status"] == "ok"
        assert hash_step["detail"] == "first ingestion"

    @pytest.mark.asyncio
    async def test_skip_clears_error_message(self, db, workspace):
        """When hash matches, error_message from a previous failure is cleared."""
        bot = await make_chatbot(db, workspace)
        kb = await make_knowledge_base(db, workspace, bot)
        content = "Some content"
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        doc = await make_document(
            db, workspace, kb,
            source_type="text", raw_content=content, status="stale",
        )
        doc.content_hash = content_hash
        doc.error_message = "Previous HTTP 500 error"
        await db.flush()

        await run_ingestion(db, doc.id)

        await db.refresh(doc)
        assert doc.error_message is None
        assert doc.status == "indexed"
