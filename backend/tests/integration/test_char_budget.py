"""Integration tests for character budget enforcement."""
import asyncio
import uuid
import pytest

from app.models.knowledge import Document, KnowledgeBase
from app.models.organizational import Workspace
from app.services.ingestion.pipeline import run_ingestion
from sqlalchemy import select


@pytest.fixture
async def kb(db, workspace):
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        name="test kb",
    )
    db.add(kb)
    await db.flush()
    return kb


async def _make_doc(db, workspace, kb, content: str) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        knowledge_base_id=kb.id,
        source_type="text",
        raw_content=content,
        title="test",
        status="pending",
    )
    db.add(doc)
    await db.flush()
    return doc


class TestCharBudget:

    async def test_ingest_sets_char_count(self, db, workspace, kb):
        """After ingestion, document.char_count equals len(raw_content)."""
        content = "hello world"
        doc = await _make_doc(db, workspace, kb, content)

        # Set plan limit high so budget is not exceeded
        workspace.plan = "starter"
        await db.flush()

        await run_ingestion(db, doc.id)

        await db.flush()
        await db.refresh(doc)
        assert doc.char_count == len(content)
        assert doc.status == "indexed"

    async def test_budget_exceeded_sets_skipped(self, db, workspace, kb):
        """When chars_indexed would exceed plan limit, document is skipped."""
        # Set workspace to free plan (500k limit) and pre-fill chars_indexed near limit
        workspace.plan = "free"
        workspace.chars_indexed = 499_999  # 1 char remaining
        await db.flush()

        content = "hello world"  # 11 chars — would exceed the 1 char remaining
        doc = await _make_doc(db, workspace, kb, content)
        await run_ingestion(db, doc.id)

        await db.flush()
        await db.refresh(doc)
        await db.refresh(workspace)
        assert doc.status == "skipped"
        assert doc.char_count == 0
        # chars_indexed must not have increased
        assert workspace.chars_indexed == 499_999

    async def test_enterprise_plan_has_no_limit(self, db, workspace, kb):
        """Enterprise plan (limit=None) always accepts budget."""
        workspace.plan = "enterprise"
        workspace.chars_indexed = 50_000_000  # already huge
        await db.flush()

        content = "a" * 1000
        doc = await _make_doc(db, workspace, kb, content)
        await run_ingestion(db, doc.id)

        await db.flush()
        await db.refresh(doc)
        assert doc.status == "indexed"
        assert doc.char_count == 1000

    async def test_delete_decrements_chars_indexed(self, db, workspace, kb):
        """Deleting an indexed document decrements workspace.chars_indexed."""
        from app.services.document_service import delete_document

        workspace.plan = "starter"
        workspace.chars_indexed = 0
        await db.flush()

        content = "hello world"
        doc = await _make_doc(db, workspace, kb, content)
        await run_ingestion(db, doc.id)
        await db.flush()

        await db.refresh(workspace)
        chars_before = workspace.chars_indexed
        assert chars_before == len(content)

        await delete_document(db, workspace.id, doc.id)

        await db.refresh(workspace)
        assert workspace.chars_indexed == 0

    @pytest.mark.skip(
        reason="Requires commits visible across sessions; "
               "incompatible with savepoint-based test fixtures (db.commit() only releases savepoint)"
    )
    async def test_concurrent_ingest_does_not_exceed_limit(self, db, workspace, kb):
        """Two concurrent ingestions for the same workspace respect the atomic limit.

        Uses two separate sessions (as real Celery tasks would) to test the
        atomic UPDATE...WHERE...RETURNING pattern. A single shared session
        cannot test concurrency correctly.
        """
        from app.database import async_session_factory, engine as app_engine

        workspace.plan = "free"
        workspace.chars_indexed = 499_900  # 100 chars remaining
        await db.commit()  # commit so both sessions see the workspace

        content = "x" * 60  # 60 chars each — together 120 > 100 remaining

        # Create both documents in the shared session
        doc1_id = (await _make_doc(db, workspace, kb, content)).id
        doc2_id = (await _make_doc(db, workspace, kb, content)).id
        await db.commit()

        # Run ingestion in two separate sessions — mimics two Celery workers
        async def ingest_in_own_session(doc_id):
            await app_engine.dispose()
            async with async_session_factory() as sess:
                await run_ingestion(sess, doc_id)
                await sess.commit()

        await asyncio.gather(
            ingest_in_own_session(doc1_id),
            ingest_in_own_session(doc2_id),
        )

        # Read back results from a fresh session
        await app_engine.dispose()
        async with async_session_factory() as check_sess:
            from sqlalchemy import select as sa_select
            from app.models.knowledge import Document
            from app.models.organizational import Workspace

            r1 = await check_sess.execute(sa_select(Document).where(Document.id == doc1_id))
            r2 = await check_sess.execute(sa_select(Document).where(Document.id == doc2_id))
            ws = (await check_sess.execute(sa_select(Workspace).where(Workspace.id == workspace.id))).scalar_one()

            doc1_status = r1.scalar_one().status
            doc2_status = r2.scalar_one().status

        statuses = {doc1_status, doc2_status}
        assert "indexed" in statuses
        assert "skipped" in statuses
        assert ws.chars_indexed <= 500_000
