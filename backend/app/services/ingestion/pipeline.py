import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.integrations import IntegrationConfig
from app.models.knowledge import Document
from app.services.ingestion.chunkers.markdown_chunker import chunk_markdown
from app.services.ingestion.chunkers.qa_chunker import chunk_qa
from app.services.ingestion.chunkers.recursive_chunker import chunk_recursive
from app.services.ingestion.embedder import embed_chunks
from app.services.ingestion.extractors.csv_extractor import extract_from_csv
from app.services.ingestion.extractors.docx_extractor import extract_from_docx
from app.services.ingestion.extractors.pdf_extractor import extract_from_pdf
from app.services.ingestion.extractors.text_extractor import extract_from_text
from app.services.ingestion.extractors.sitemap_extractor import extract_urls_from_sitemap
from app.services.ingestion.extractors.url_extractor import extract_from_url
from app.services.ingestion.vector_store import delete_by_document, insert_chunks
from app.services.realtime import emit_to_workspace, write_document_active, clear_document_active

logger = logging.getLogger(__name__)


async def run_ingestion(db: AsyncSession, document_id: uuid.UUID) -> None:
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        logger.error(f"Document {document_id} not found")
        return

    document.status = "processing"
    await db.flush()

    await write_document_active(
        str(document.workspace_id), str(document.id),
        document.title or "", str(document.knowledge_base_id), "processing",
    )
    await emit_to_workspace(str(document.workspace_id), "document:status_changed", {
        "document_id": str(document.id),
        "knowledge_base_id": str(document.knowledge_base_id),
        "status": "processing",
        "char_count": 0,
        "title": document.title or "",
        "error_message": None,
    })

    steps: list[dict] = []

    def _record(
        step: str,
        status: str,
        t0: datetime,
        detail: str | None = None,
        error: str | None = None,
    ) -> None:
        steps.append({
            "step": step,
            "status": status,
            "started_at": t0.isoformat(),
            "duration_ms": int((datetime.now(timezone.utc) - t0).total_seconds() * 1000),
            "detail": detail,
            "error": error,
        })

    # SITEMAP: fan out to per-URL child documents
    if document.source_type == "sitemap":
        if not document.source_url:
            document.status = "failed"
            document.error_message = "source_url required for sitemap"
            document.ingestion_steps = steps
            await db.commit()
            return

        t0 = datetime.now(timezone.utc)
        try:
            urls = extract_urls_from_sitemap(document.source_url)
            _record("extract_sources", "ok", t0, detail=f"{len(urls)} sources discovered")
        except ValueError as exc:
            logger.error(f"Sitemap extraction failed for {document.source_url}: {exc}")
            _record("extract_sources", "failed", t0, error=str(exc))
            document.status = "failed"
            document.error_message = str(exc)
            document.ingestion_steps = steps
            await db.commit()
            raise

        new_children: list[Document] = []
        t0 = datetime.now(timezone.utc)
        for url in urls:
            child = Document(
                workspace_id=document.workspace_id,
                knowledge_base_id=document.knowledge_base_id,
                source_type="url",
                source_url=url,
                title=url,
                status="pending",
                sync_frequency=document.sync_frequency,
            )
            db.add(child)
            new_children.append(child)

        await db.flush()  # assign IDs
        child_ids = [str(child.id) for child in new_children]
        _record("fan_out", "ok", t0, detail=f"{len(new_children)} child documents queued")

        document.status = "indexed"
        document.chunk_count = len(urls)
        document.last_indexed_at = datetime.now(timezone.utc)
        document.ingestion_steps = steps
        await db.commit()

        from app.workers.tasks.ingest_document import ingest_document

        for child_id in child_ids:
            ingest_document.delay(child_id)  # type: ignore[attr-defined]
        return

    # NOTION: fetch page content via Notion API
    if document.source_type == "notion":
        if not document.source_url:
            document.status = "failed"
            document.error_message = "source_url required for notion"
            document.ingestion_steps = steps
            await db.commit()
            return
        notion_result = await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.workspace_id == document.workspace_id,
                IntegrationConfig.integration_type == "notion",
                IntegrationConfig.is_active == True,  # noqa: E712
            )
        )
        notion_integration = notion_result.scalar_one_or_none()
        if not notion_integration:
            document.status = "failed"
            document.error_message = f"No Notion integration configured for workspace {document.workspace_id}"
            document.ingestion_steps = steps
            logger.error(document.error_message)
            await db.commit()
            return
        from app.services.ingestion.extractors.notion_extractor import extract_from_notion

        access_token = notion_integration.config.get("access_token", "")
        if settings.FERNET_KEY and access_token:
            from cryptography.fernet import Fernet

            f = Fernet(settings.FERNET_KEY.encode())
            access_token = f.decrypt(access_token.encode()).decode()

        t0 = datetime.now(timezone.utc)
        try:
            content = await extract_from_notion(document.source_url, access_token)
            _record("extract", "ok", t0, detail=f"{len(content)} chars extracted")
        except Exception as exc:
            _record("extract", "failed", t0, error=str(exc))
            document.status = "failed"
            document.error_message = str(exc)
            document.ingestion_steps = steps
            await db.commit()
            raise

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
        try:
            texts = [c["content"] for c in chunks]
            embeddings = await embed_chunks(texts)
            _record("embed", "ok", t0, detail=f"{len(embeddings)} embeddings generated")
        except Exception as exc:
            _record("embed", "failed", t0, error=str(exc))
            document.status = "failed"
            document.error_message = str(exc)
            document.ingestion_steps = steps
            await db.commit()
            raise

        t0 = datetime.now(timezone.utc)
        try:
            await delete_by_document(db, document.id)
            count = await insert_chunks(
                db,
                workspace_id=document.workspace_id,
                document_id=document.id,
                knowledge_base_id=document.knowledge_base_id,
                chunks=chunks,
                embeddings=embeddings,
            )
            _record("index", "ok", t0, detail=f"{count} vectors stored")
        except Exception as exc:
            _record("index", "failed", t0, error=str(exc))
            document.status = "failed"
            document.error_message = str(exc)
            document.ingestion_steps = steps
            await db.commit()
            raise

        document.status = "indexed"
        document.chunk_count = count
        document.last_indexed_at = datetime.now(timezone.utc)
        document.ingestion_steps = steps
        return

    # GOOGLE DRIVE: fetch content via Drive API
    if document.source_type == "google_drive":
        if not document.source_url:
            document.status = "failed"
            document.error_message = "source_url required for google_drive"
            document.ingestion_steps = steps
            await db.commit()
            return
        from app.services.ingestion.extractors.google_drive_extractor import extract_from_google_drive

        t0 = datetime.now(timezone.utc)
        try:
            content = await extract_from_google_drive(document.source_url, str(document.workspace_id), db)
            _record("extract", "ok", t0, detail=f"{len(content)} chars extracted")
        except Exception as exc:
            _record("extract", "failed", t0, error=str(exc))
            document.status = "failed"
            document.error_message = str(exc)
            document.ingestion_steps = steps
            await db.commit()
            raise

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
        try:
            texts = [c["content"] for c in chunks]
            embeddings = await embed_chunks(texts)
            _record("embed", "ok", t0, detail=f"{len(embeddings)} embeddings generated")
        except Exception as exc:
            _record("embed", "failed", t0, error=str(exc))
            document.status = "failed"
            document.error_message = str(exc)
            document.ingestion_steps = steps
            await db.commit()
            raise

        t0 = datetime.now(timezone.utc)
        try:
            await delete_by_document(db, document.id)
            count = await insert_chunks(
                db,
                workspace_id=document.workspace_id,
                document_id=document.id,
                knowledge_base_id=document.knowledge_base_id,
                chunks=chunks,
                embeddings=embeddings,
            )
            _record("index", "ok", t0, detail=f"{count} vectors stored")
        except Exception as exc:
            _record("index", "failed", t0, error=str(exc))
            document.status = "failed"
            document.error_message = str(exc)
            document.ingestion_steps = steps
            await db.commit()
            raise

        document.status = "indexed"
        document.chunk_count = count
        document.last_indexed_at = datetime.now(timezone.utc)
        document.ingestion_steps = steps
        return

    # DROPBOX: fetch and concatenate text content from Dropbox files
    if document.source_type == "dropbox":
        from app.services.ingestion.extractors.dropbox_extractor import extract_from_dropbox

        t0 = datetime.now(timezone.utc)
        try:
            parts: list[str] = []
            async for chunk in extract_from_dropbox(document.source_url or "", str(document.workspace_id), db):
                parts.append(chunk)
            content = "".join(parts)
            _record("extract", "ok", t0, detail=f"{len(content)} chars extracted")
        except Exception as exc:
            _record("extract", "failed", t0, error=str(exc))
            document.status = "failed"
            document.error_message = str(exc)
            document.ingestion_steps = steps
            await db.commit()
            raise

        if not content.strip():
            t0_chunk = datetime.now(timezone.utc)
            _record("chunk", "skipped", t0_chunk, detail="no chunks (empty content)")
            document.status = "indexed"
            document.chunk_count = 0
            document.last_indexed_at = datetime.now(timezone.utc)
            document.ingestion_steps = steps
            return

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
        try:
            texts = [c["content"] for c in chunks]
            embeddings = await embed_chunks(texts)
            _record("embed", "ok", t0, detail=f"{len(embeddings)} embeddings generated")
        except Exception as exc:
            _record("embed", "failed", t0, error=str(exc))
            document.status = "failed"
            document.error_message = str(exc)
            document.ingestion_steps = steps
            await db.commit()
            raise

        t0 = datetime.now(timezone.utc)
        try:
            await delete_by_document(db, document.id)
            count = await insert_chunks(
                db,
                workspace_id=document.workspace_id,
                document_id=document.id,
                knowledge_base_id=document.knowledge_base_id,
                chunks=chunks,
                embeddings=embeddings,
            )
            _record("index", "ok", t0, detail=f"{count} vectors stored")
        except Exception as exc:
            _record("index", "failed", t0, error=str(exc))
            document.status = "failed"
            document.error_message = str(exc)
            document.ingestion_steps = steps
            await db.commit()
            raise

        document.status = "indexed"
        document.chunk_count = count
        document.last_indexed_at = datetime.now(timezone.utc)
        document.ingestion_steps = steps
        return

    # SALESFORCE: fan out to one child Document per Knowledge article
    if document.source_type == "salesforce":
        from app.services.ingestion.extractors.salesforce_extractor import extract_from_salesforce

        new_children_sf: list[Document] = []
        t0 = datetime.now(timezone.utc)
        try:
            async for article in extract_from_salesforce(document.source_url or "", str(document.workspace_id), db):
                child = Document(
                    workspace_id=document.workspace_id,
                    knowledge_base_id=document.knowledge_base_id,
                    source_type="url",
                    source_url=article["source_url"],
                    title=article["title"],
                    raw_content=article["content"],
                    status="pending",
                    sync_frequency=document.sync_frequency,
                )
                db.add(child)
                new_children_sf.append(child)
            _record("extract_sources", "ok", t0, detail=f"{len(new_children_sf)} sources discovered")
        except Exception as exc:
            _record("extract_sources", "failed", t0, error=str(exc))
            document.status = "failed"
            document.error_message = str(exc)
            document.ingestion_steps = steps
            await db.commit()
            raise

        await db.flush()  # assign IDs

        # Override source_type to "text" so _extract() reads raw_content
        t0 = datetime.now(timezone.utc)
        for child in new_children_sf:
            child.source_type = "text"
        await db.flush()
        child_ids = [str(child.id) for child in new_children_sf]
        _record("fan_out", "ok", t0, detail=f"{len(new_children_sf)} child documents queued")

        document.status = "indexed"
        document.chunk_count = len(new_children_sf)
        document.last_indexed_at = datetime.now(timezone.utc)
        document.ingestion_steps = steps
        await db.commit()

        # Ingest each article child asynchronously
        from app.workers.tasks.ingest_document import ingest_document

        for child_id in child_ids:
            ingest_document.delay(child_id)  # type: ignore[attr-defined]
        return

    # ZENDESK: fan out to one child Document per Help Center article
    if document.source_type == "zendesk":
        if not document.source_url:
            document.status = "failed"
            document.error_message = "source_url required for zendesk"
            document.ingestion_steps = steps
            await db.commit()
            return
        from app.services.ingestion.extractors.zendesk_extractor import extract_from_zendesk

        new_children_zd: list[Document] = []
        t0 = datetime.now(timezone.utc)
        try:
            async for article in extract_from_zendesk(document.source_url, str(document.workspace_id), db):
                child = Document(
                    workspace_id=document.workspace_id,
                    knowledge_base_id=document.knowledge_base_id,
                    source_type="url",
                    source_url=article["source_url"],
                    title=article["title"],
                    raw_content=article["content"],
                    status="pending",
                    sync_frequency=document.sync_frequency,
                )
                db.add(child)
                new_children_zd.append(child)
            _record("extract_sources", "ok", t0, detail=f"{len(new_children_zd)} sources discovered")
        except Exception as exc:
            _record("extract_sources", "failed", t0, error=str(exc))
            document.status = "failed"
            document.error_message = str(exc)
            document.ingestion_steps = steps
            await db.commit()
            raise

        await db.flush()  # assign IDs

        # Override source_type to "text" so _extract() reads raw_content
        t0 = datetime.now(timezone.utc)
        for child in new_children_zd:
            child.source_type = "text"
        await db.flush()
        child_ids = [str(child.id) for child in new_children_zd]
        _record("fan_out", "ok", t0, detail=f"{len(new_children_zd)} child documents queued")

        document.status = "indexed"
        document.chunk_count = len(new_children_zd)
        document.last_indexed_at = datetime.now(timezone.utc)
        document.ingestion_steps = steps
        await db.commit()

        # Ingest each article child asynchronously
        from app.workers.tasks.ingest_document import ingest_document

        for child_id in child_ids:
            ingest_document.delay(child_id)  # type: ignore[attr-defined]
        return

    # STANDARD PATH: url / file / text / qa
    t0 = datetime.now(timezone.utc)
    try:
        content = _extract(document)
        _record("extract", "ok", t0, detail=f"{len(content)} chars extracted")
    except Exception as exc:
        _record("extract", "failed", t0, error=str(exc))
        document.status = "failed"
        document.error_message = str(exc)
        document.ingestion_steps = steps
        await db.commit()

        await clear_document_active(str(document.workspace_id), str(document.id))
        await emit_to_workspace(str(document.workspace_id), "document:status_changed", {
            "document_id": str(document.id),
            "knowledge_base_id": str(document.knowledge_base_id),
            "status": "failed",
            "char_count": 0,
            "title": document.title or "",
            "error_message": str(exc),
        })
        raise

    # Content hash check — skip re-ingestion if content unchanged
    t0 = datetime.now(timezone.utc)
    new_hash = hashlib.sha256(content.encode()).hexdigest()
    if document.content_hash == new_hash:
        _record("hash_check", "skipped", t0, detail="content unchanged")
        document.status = "indexed"
        document.error_message = None
        document.last_indexed_at = datetime.now(timezone.utc)
        document.ingestion_steps = steps
        logger.info("Document %s: content unchanged, skipping re-ingestion", document_id)
        await db.flush()
        return
    _record("hash_check", "ok", t0, detail="content changed" if document.content_hash else "first ingestion")
    document.content_hash = new_hash

    # Character budget enforcement
    n = len(content)
    if n > 0:
        from app.config import PLAN_CHAR_LIMITS
        from app.models.organizational import Workspace

        t0 = datetime.now(timezone.utc)
        ws_result = await db.execute(
            select(Workspace).where(Workspace.id == document.workspace_id)
        )
        workspace = ws_result.scalar_one()
        limit = PLAN_CHAR_LIMITS.get(workspace.plan)

        # COALESCE(CAST(:limit AS BIGINT), max-bigint) handles the unlimited-plan
        # case (limit=None) without a NULL IS NULL check, which asyncpg cannot
        # type-infer for untyped None parameters.
        budget_rows = await db.execute(
            sa_text("""
                UPDATE workspaces
                SET    chars_indexed = chars_indexed + :n
                WHERE  id = :workspace_id
                  AND  chars_indexed + :n <= COALESCE(CAST(:limit AS BIGINT), 9223372036854775807)
                RETURNING chars_indexed
            """),
            {"n": n, "workspace_id": document.workspace_id, "limit": limit},
        )
        accepted = budget_rows.fetchone() is not None

        if not accepted:
            _record("budget_check", "skipped", t0, detail="over limit — document skipped")
            document.status = "skipped"
            document.char_count = 0
            document.ingestion_steps = steps
            await db.flush()

            await clear_document_active(str(document.workspace_id), str(document.id))
            await emit_to_workspace(str(document.workspace_id), "document:status_changed", {
                "document_id": str(document.id),
                "knowledge_base_id": str(document.knowledge_base_id),
                "status": "skipped",
                "char_count": 0,
                "title": document.title or "",
                "error_message": "Character limit reached",
            })
            return

        _record("budget_check", "ok", t0, detail=f"{n} chars accepted")
        document.char_count = n

        # Emit updated usage
        ws_refresh = await db.execute(
            select(Workspace.chars_indexed, Workspace.plan).where(Workspace.id == document.workspace_id)
        )
        ws_row = ws_refresh.one()
        await emit_to_workspace(str(document.workspace_id), "workspace:usage_updated", {
            "chars_indexed": ws_row.chars_indexed,
            "chars_limit": PLAN_CHAR_LIMITS.get(ws_row.plan, 0),
            "plan": ws_row.plan,
        })

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
        document.status = "failed"
        document.error_message = str(exc)
        document.ingestion_steps = steps
        await db.commit()

        await clear_document_active(str(document.workspace_id), str(document.id))
        await emit_to_workspace(str(document.workspace_id), "document:status_changed", {
            "document_id": str(document.id),
            "knowledge_base_id": str(document.knowledge_base_id),
            "status": "failed",
            "char_count": 0,
            "title": document.title or "",
            "error_message": str(exc),
        })
        raise

    t0 = datetime.now(timezone.utc)
    try:
        texts = [c["content"] for c in chunks]
        embeddings = await embed_chunks(texts)
        _record("embed", "ok", t0, detail=f"{len(embeddings)} embeddings generated")
    except Exception as exc:
        _record("embed", "failed", t0, error=str(exc))
        document.status = "failed"
        document.error_message = str(exc)
        document.ingestion_steps = steps
        await db.commit()

        await clear_document_active(str(document.workspace_id), str(document.id))
        await emit_to_workspace(str(document.workspace_id), "document:status_changed", {
            "document_id": str(document.id),
            "knowledge_base_id": str(document.knowledge_base_id),
            "status": "failed",
            "char_count": 0,
            "title": document.title or "",
            "error_message": str(exc),
        })
        raise

    t0 = datetime.now(timezone.utc)
    try:
        await delete_by_document(db, document.id)
        count = await insert_chunks(
            db,
            workspace_id=document.workspace_id,
            document_id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            chunks=chunks,
            embeddings=embeddings,
        )
        _record("index", "ok", t0, detail=f"{count} vectors stored")
    except Exception as exc:
        _record("index", "failed", t0, error=str(exc))
        document.status = "failed"
        document.error_message = str(exc)
        document.ingestion_steps = steps
        await db.commit()

        await clear_document_active(str(document.workspace_id), str(document.id))
        await emit_to_workspace(str(document.workspace_id), "document:status_changed", {
            "document_id": str(document.id),
            "knowledge_base_id": str(document.knowledge_base_id),
            "status": "failed",
            "char_count": 0,
            "title": document.title or "",
            "error_message": str(exc),
        })
        raise

    document.status = "indexed"
    document.chunk_count = count
    document.last_indexed_at = datetime.now(timezone.utc)
    document.ingestion_steps = steps
    await db.flush()

    await clear_document_active(str(document.workspace_id), str(document.id))
    await emit_to_workspace(str(document.workspace_id), "document:status_changed", {
        "document_id": str(document.id),
        "knowledge_base_id": str(document.knowledge_base_id),
        "status": "indexed",
        "char_count": document.char_count or 0,
        "title": document.title or "",
        "error_message": None,
    })


def _extract(document: Document) -> str:
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
