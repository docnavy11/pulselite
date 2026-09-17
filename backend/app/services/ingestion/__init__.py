"""Document ingestion pipeline — consolidates services/ingestion/pipeline.py.

Simplified: one function per step, dispatches by source_type internally.
Extractors, chunkers, embedder remain in their own files.
"""
import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import IntegrationConfig
from app.models.knowledge import Document
from app.services.ingestion.chunkers.markdown_chunker import chunk_markdown
from app.services.ingestion.chunkers.qa_chunker import chunk_qa
from app.services.ingestion.chunkers.recursive_chunker import chunk_recursive
from app.services.ingestion.embedder import embed_chunks
from app.services.ingestion.vector_store import delete_by_document, insert_chunks
from app.realtime.events import notify_workspace

logger = logging.getLogger(__name__)


async def run_ingestion(db: AsyncSession, document_id: uuid.UUID) -> None:
    """Main ingestion entry point. Extracts, chunks, embeds, indexes a document."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        logger.error("Document %s not found", document_id)
        return

    document.status = "processing"
    await db.flush()

    await notify_workspace(str(document.workspace_id), "document:status_changed", {
        "document_id": str(document.id), "knowledge_base_id": str(document.knowledge_base_id),
        "status": "processing", "char_count": 0, "title": document.title or "", "error_message": None,
    })

    steps = []

    def _record(step, status, t0, detail=None, error=None):
        steps.append({
            "step": step, "status": status, "started_at": t0.isoformat(),
            "duration_ms": int((datetime.now(timezone.utc) - t0).total_seconds() * 1000),
            "detail": detail, "error": error,
        })

    # Fan-out source types (sitemap, notion, google_drive, dropbox, salesforce, zendesk)
    if document.source_type in ("sitemap", "notion", "google_drive", "dropbox", "salesforce", "zendesk"):
        await _handle_fan_out_source(db, document, steps, _record)
        return

    # Standard path: url / file / text / qa
    t0 = datetime.now(timezone.utc)
    try:
        content = await _extract(db, document)
        _record("extract", "ok", t0, detail=f"{len(content)} chars extracted")
    except Exception as exc:
        _record("extract", "failed", t0, error=str(exc))
        await _mark_failed(db, document, str(exc), steps)
        raise

    # Content hash check
    t0 = datetime.now(timezone.utc)
    new_hash = hashlib.sha256(content.encode()).hexdigest()
    if document.content_hash == new_hash:
        _record("hash_check", "skipped", t0, detail="content unchanged")
        document.status = "indexed"
        document.error_message = None
        document.last_indexed_at = datetime.now(timezone.utc)
        document.ingestion_steps = steps
        await db.flush()
        return
    _record("hash_check", "ok", t0, detail="content changed" if document.content_hash else "first ingestion")
    document.content_hash = new_hash

    # Character budget enforcement
    n = len(content)
    if n > 0:
        t0 = datetime.now(timezone.utc)
        accepted = await _check_budget(db, document, n)
        if not accepted:
            _record("budget_check", "skipped", t0, detail="over limit — document skipped")
            document.status = "skipped"
            document.char_count = 0
            document.ingestion_steps = steps
            await db.flush()
            await notify_workspace(str(document.workspace_id), "document:status_changed", {
                "document_id": str(document.id), "knowledge_base_id": str(document.knowledge_base_id),
                "status": "skipped", "char_count": 0, "title": document.title or "", "error_message": "Character limit reached",
            })
            return
        _record("budget_check", "ok", t0, detail=f"{n} chars accepted")
        document.char_count = n

    # Chunk
    t0 = datetime.now(timezone.utc)
    try:
        chunks = _chunk(document, content)
        if not chunks:
            _record("chunk", "skipped", t0, detail="no chunks (empty content)")
            document.status = "indexed"
            document.chunk_count = 0
            document.last_indexed_at = datetime.now(timezone.utc)
            document.ingestion_steps = steps
            await db.flush()
            return
        _record("chunk", "ok", t0, detail=f"{len(chunks)} chunks produced")
    except Exception as exc:
        _record("chunk", "failed", t0, error=str(exc))
        await _mark_failed(db, document, str(exc), steps)
        raise

    # Embed
    t0 = datetime.now(timezone.utc)
    try:
        texts = [c["content"] for c in chunks]
        embeddings = await embed_chunks(texts)
        _record("embed", "ok", t0, detail=f"{len(embeddings)} embeddings generated")
    except Exception as exc:
        _record("embed", "failed", t0, error=str(exc))
        await _mark_failed(db, document, str(exc), steps)
        raise

    # Index
    t0 = datetime.now(timezone.utc)
    try:
        await delete_by_document(db, document.id)
        count = await insert_chunks(db, workspace_id=document.workspace_id, document_id=document.id,
                                     knowledge_base_id=document.knowledge_base_id, chunks=chunks, embeddings=embeddings)
        _record("index", "ok", t0, detail=f"{count} vectors stored")
    except Exception as exc:
        _record("index", "failed", t0, error=str(exc))
        await _mark_failed(db, document, str(exc), steps)
        raise

    document.status = "indexed"
    document.chunk_count = count
    document.last_indexed_at = datetime.now(timezone.utc)
    document.ingestion_steps = steps
    await db.flush()

    await notify_workspace(str(document.workspace_id), "document:status_changed", {
        "document_id": str(document.id), "knowledge_base_id": str(document.knowledge_base_id),
        "status": "indexed", "char_count": document.char_count or 0, "title": document.title or "", "error_message": None,
    })


async def _extract(db: AsyncSession, document: Document) -> str:
    """Extract text content from a document based on its source_type."""
    from app.services.ingestion.extractors.text_extractor import extract_from_text
    from app.services.ingestion.extractors.url_extractor import extract_from_url
    from app.services.ingestion.extractors.pdf_extractor import extract_from_pdf
    from app.services.ingestion.extractors.docx_extractor import extract_from_docx
    from app.services.ingestion.extractors.csv_extractor import extract_from_csv

    match document.source_type:
        case "url" | "sitemap":
            if not document.source_url:
                raise ValueError("source_url required for url/sitemap source type")
            return extract_from_url(document.source_url)
        case "file":
            if not document.file_path:
                raise ValueError("file_path required for file source type")
            if document.file_path.endswith(".pdf"):
                return extract_from_pdf(document.file_path)
            elif document.file_path.endswith(".docx"):
                return extract_from_docx(document.file_path)
            elif document.file_path.endswith(".csv"):
                return extract_from_csv(document.file_path)
            else:
                with open(document.file_path) as f:
                    return f.read()
        case "text" | "qa":
            if not document.raw_content:
                raise ValueError("raw_content required for text/qa source type")
            return extract_from_text(document.raw_content)
        case _:
            raise ValueError(f"Unsupported source type: {document.source_type}")


def _chunk(document: Document, content: str) -> list[dict]:
    if document.source_type == "qa":
        return chunk_qa(content)
    has_headings = any(line.startswith("#") for line in content.split("\n")[:50])
    if has_headings:
        return chunk_markdown(content)
    return chunk_recursive(content)


async def _check_budget(db: AsyncSession, document: Document, n: int) -> bool:
    from app.services.plan_service import get_plan_limits
    from app.models.organizational import Workspace
    ws_result = await db.execute(select(Workspace).where(Workspace.id == document.workspace_id))
    workspace = ws_result.scalar_one()
    _limits = get_plan_limits(workspace.plan)
    limit = _limits["chars_indexed"] if _limits["chars_indexed"] != -1 else None
    budget_rows = await db.execute(
        sa_text("""
            UPDATE workspaces SET chars_indexed = chars_indexed + :n
            WHERE id = :workspace_id
              AND chars_indexed + :n <= COALESCE(CAST(:limit AS BIGINT), 9223372036854775807)
            RETURNING chars_indexed
        """),
        {"n": n, "workspace_id": document.workspace_id, "limit": limit},
    )
    return budget_rows.fetchone() is not None


async def _mark_failed(db: AsyncSession, document: Document, error: str, steps: list):
    document.status = "failed"
    document.error_message = error
    document.ingestion_steps = steps
    await db.commit()
    await notify_workspace(str(document.workspace_id), "document:status_changed", {
        "document_id": str(document.id), "knowledge_base_id": str(document.knowledge_base_id),
        "status": "failed", "char_count": 0, "title": document.title or "", "error_message": error,
    })


async def _handle_fan_out_source(db: AsyncSession, document: Document, steps: list, _record):
    """Handle source types that fan out to child documents (sitemap, notion, integrations)."""
    from app.background.runner import enqueue

    t0 = datetime.now(timezone.utc)

    if document.source_type == "sitemap":
        from app.services.ingestion.extractors.sitemap_extractor import extract_urls_from_sitemap
        if not document.source_url:
            document.status = "failed"
            document.error_message = "source_url required for sitemap"
            document.ingestion_steps = steps
            await db.commit()
            return
        urls = await extract_urls_from_sitemap(document.source_url)
        _record("extract_sources", "ok", t0, detail=f"{len(urls)} sources discovered")
        children = []
        for url in urls:
            child = Document(workspace_id=document.workspace_id, knowledge_base_id=document.knowledge_base_id,
                             source_type="url", source_url=url, title=url, status="pending", sync_frequency=document.sync_frequency)
            db.add(child)
            children.append(child)
        await db.flush()
        document.status = "indexed"
        document.chunk_count = len(urls)
        document.last_indexed_at = datetime.now(timezone.utc)
        document.ingestion_steps = steps
        await db.commit()
        for child in children:
            enqueue(_ingest_child(child.id), name=f"ingest:{child.id}")
        return

    if document.source_type == "notion":
        from app.services.ingestion.extractors.notion_extractor import extract_from_notion
        from app.config import settings
        if not document.source_url:
            document.status = "failed"
            document.error_message = "source_url required for notion"
            await db.commit()
            return
        notion_result = await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.workspace_id == document.workspace_id,
                IntegrationConfig.integration_type == "notion", IntegrationConfig.is_active == True,
            )
        )
        notion_integration = notion_result.scalar_one_or_none()
        if not notion_integration:
            document.status = "failed"
            document.error_message = "No Notion integration configured"
            await db.commit()
            return
        access_token = notion_integration.config.get("access_token", "")
        if settings.FERNET_KEY and access_token:
            from cryptography.fernet import Fernet
            f = Fernet(settings.FERNET_KEY.encode())
            access_token = f.decrypt(access_token.encode()).decode()
        content = await extract_from_notion(document.source_url, access_token)
        _record("extract", "ok", t0, detail=f"{len(content)} chars extracted")
        # Continue with standard chunk/embed/index
        await _standard_ingest(db, document, content, steps, _record)
        return

    # For google_drive, dropbox, salesforce, zendesk — similar fan-out pattern
    if document.source_type in ("salesforce", "zendesk"):
        extractor_map = {
            "salesforce": "app.services.ingestion.extractors.salesforce_extractor",
            "zendesk": "app.services.ingestion.extractors.zendesk_extractor",
        }
        func_map = {"salesforce": "extract_from_salesforce", "zendesk": "extract_from_zendesk"}
        import importlib
        mod = importlib.import_module(extractor_map[document.source_type])
        extract_fn = getattr(mod, func_map[document.source_type])
        children = []
        async for article in extract_fn(document.source_url or "", str(document.workspace_id), db):
            child = Document(
                workspace_id=document.workspace_id, knowledge_base_id=document.knowledge_base_id,
                source_type="text", source_url=article.get("source_url"), title=article["title"],
                raw_content=article["content"], status="pending", sync_frequency=document.sync_frequency,
            )
            db.add(child)
            children.append(child)
        await db.flush()
        _record("extract_sources", "ok", t0, detail=f"{len(children)} sources discovered")
        document.status = "indexed"
        document.chunk_count = len(children)
        document.last_indexed_at = datetime.now(timezone.utc)
        document.ingestion_steps = steps
        await db.commit()
        for child in children:
            enqueue(_ingest_child(child.id), name=f"ingest:{child.id}")
        return

    if document.source_type == "google_drive":
        from app.services.ingestion.extractors.google_drive_extractor import extract_from_google_drive
        if not document.source_url:
            document.status = "failed"
            document.error_message = "source_url required for google_drive"
            await db.commit()
            return
        content = await extract_from_google_drive(document.source_url, str(document.workspace_id), db)
        _record("extract", "ok", t0, detail=f"{len(content)} chars extracted")
        await _standard_ingest(db, document, content, steps, _record)
        return

    if document.source_type == "dropbox":
        from app.services.ingestion.extractors.dropbox_extractor import extract_from_dropbox
        parts = []
        async for chunk in extract_from_dropbox(document.source_url or "", str(document.workspace_id), db):
            parts.append(chunk)
        content = "".join(parts)
        _record("extract", "ok", t0, detail=f"{len(content)} chars extracted")
        await _standard_ingest(db, document, content, steps, _record)
        return


async def _standard_ingest(db, document, content, steps, _record):
    """Standard chunk → embed → index path for already-extracted content."""
    t0 = datetime.now(timezone.utc)
    chunks = _chunk(document, content)
    if not chunks:
        _record("chunk", "skipped", t0, detail="no chunks (empty content)")
        document.status = "indexed"
        document.chunk_count = 0
        document.last_indexed_at = datetime.now(timezone.utc)
        document.ingestion_steps = steps
        return
    _record("chunk", "ok", t0, detail=f"{len(chunks)} chunks produced")

    t0 = datetime.now(timezone.utc)
    texts = [c["content"] for c in chunks]
    embeddings = await embed_chunks(texts)
    _record("embed", "ok", t0, detail=f"{len(embeddings)} embeddings generated")

    t0 = datetime.now(timezone.utc)
    await delete_by_document(db, document.id)
    count = await insert_chunks(db, workspace_id=document.workspace_id, document_id=document.id,
                                 knowledge_base_id=document.knowledge_base_id, chunks=chunks, embeddings=embeddings)
    _record("index", "ok", t0, detail=f"{count} vectors stored")

    document.status = "indexed"
    document.chunk_count = count
    document.last_indexed_at = datetime.now(timezone.utc)
    document.ingestion_steps = steps


async def _ingest_child(document_id: uuid.UUID):
    """Ingest a child document in a fresh session."""
    from app.database import async_session_factory
    async with async_session_factory() as db:
        await run_ingestion(db, document_id)
        await db.commit()
