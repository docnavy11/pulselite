"""Integration tests: pipeline writes ingestion_steps and error_message."""
import uuid
import pytest
from app.models.knowledge import Document, KnowledgeBase
from app.services.ingestion.pipeline import run_ingestion


@pytest.fixture
async def kb(db, workspace):
    kb = KnowledgeBase(id=uuid.uuid4(), workspace_id=workspace.id, name="test kb")
    db.add(kb)
    await db.flush()
    return kb


async def _make_doc(db, workspace, kb, content="hello world") -> Document:
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


class TestIngestionSteps:

    async def test_success_path_records_all_steps(self, db, workspace, kb):
        """Successful ingestion writes step records for each pipeline stage."""
        doc = await _make_doc(db, workspace, kb, "hello world " * 100)
        workspace.plan = "starter"
        await db.flush()

        await run_ingestion(db, doc.id)
        await db.refresh(doc)

        assert doc.ingestion_steps is not None
        step_names = [s["step"] for s in doc.ingestion_steps]
        assert "extract" in step_names
        assert "budget_check" in step_names
        assert "chunk" in step_names
        assert "embed" in step_names
        assert "index" in step_names
        assert all(s["status"] == "ok" for s in doc.ingestion_steps)
        assert all(isinstance(s["duration_ms"], int) for s in doc.ingestion_steps)

    async def test_extract_failure_records_error_and_commits(self, db, workspace, kb):
        """When extract fails, ingestion_steps and error_message are committed before re-raise."""
        doc = Document(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            knowledge_base_id=kb.id,
            source_type="text",
            raw_content=None,   # will cause ValueError in extract_from_text
            title="bad",
            status="pending",
        )
        db.add(doc)
        await db.flush()

        with pytest.raises(Exception):
            await run_ingestion(db, doc.id)

        # Simulate the Celery task's session.rollback() — evict identity-map cache.
        # If the pipeline did NOT commit before raising, refresh() would return
        # the pre-pipeline DB state (status="pending", ingestion_steps=None).
        db.expire(doc)
        await db.refresh(doc)
        assert doc.status == "failed"
        assert doc.error_message is not None
        assert doc.ingestion_steps is not None
        assert doc.ingestion_steps[0]["step"] == "extract"
        assert doc.ingestion_steps[0]["status"] == "failed"

    async def test_budget_exceeded_records_skipped_step(self, db, workspace, kb):
        """When character budget is exceeded, budget_check step has status 'skipped'."""
        doc = await _make_doc(db, workspace, kb, "x" * 1000)
        workspace.plan = "starter"
        workspace.chars_indexed = 999_999_999  # force over limit
        await db.flush()

        await run_ingestion(db, doc.id)
        await db.refresh(doc)

        assert doc.status == "skipped"
        assert doc.ingestion_steps is not None
        budget_step = next(s for s in doc.ingestion_steps if s["step"] == "budget_check")
        assert budget_step["status"] == "skipped"
