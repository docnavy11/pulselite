import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
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

logger = logging.getLogger(__name__)


async def run_ingestion(db: AsyncSession, document_id: uuid.UUID) -> None:
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        logger.error(f"Document {document_id} not found")
        return

    document.status = "processing"
    await db.flush()

    try:
        # SITEMAP: fan out to per-URL child documents
        if document.source_type == "sitemap":
            if not document.source_url:
                document.status = "failed"
                return
            try:
                urls = extract_urls_from_sitemap(document.source_url)
            except ValueError as e:
                logger.error(f"Sitemap extraction failed for {document.source_url}: {e}")
                document.status = "failed"
                return

            new_children: list[Document] = []
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

            document.status = "indexed"
            document.chunk_count = len(urls)
            document.last_indexed_at = datetime.now(timezone.utc)
            await db.commit()

            from app.workers.tasks.ingest_document import ingest_document

            for child_id in child_ids:
                ingest_document.delay(child_id)  # type: ignore[attr-defined]
            return

        # NOTION: fetch page content via Notion API
        if document.source_type == "notion":
            if not document.source_url:
                document.status = "failed"
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
                logger.error(f"No Notion integration configured for workspace {document.workspace_id}")
                return
            from app.services.ingestion.extractors.notion_extractor import extract_from_notion

            access_token = notion_integration.config.get("access_token", "")
            if settings.FERNET_KEY and access_token:
                from cryptography.fernet import Fernet

                f = Fernet(settings.FERNET_KEY.encode())
                access_token = f.decrypt(access_token.encode()).decode()
            content = await extract_from_notion(document.source_url, access_token)
            chunks = _chunk(document, content)

            if not chunks:
                document.status = "indexed"
                document.chunk_count = 0
                document.last_indexed_at = datetime.now(timezone.utc)
                return

            texts = [c["content"] for c in chunks]
            embeddings = await embed_chunks(texts)

            await delete_by_document(db, document.id)

            count = await insert_chunks(
                db,
                workspace_id=document.workspace_id,
                document_id=document.id,
                knowledge_base_id=document.knowledge_base_id,
                chunks=chunks,
                embeddings=embeddings,
            )

            document.status = "indexed"
            document.chunk_count = count
            document.last_indexed_at = datetime.now(timezone.utc)
            return

        # GOOGLE DRIVE: fetch content via Drive API
        if document.source_type == "google_drive":
            if not document.source_url:
                document.status = "failed"
                return
            from app.services.ingestion.extractors.google_drive_extractor import extract_from_google_drive

            content = await extract_from_google_drive(document.source_url, str(document.workspace_id), db)
            chunks = _chunk(document, content)

            if not chunks:
                document.status = "indexed"
                document.chunk_count = 0
                document.last_indexed_at = datetime.now(timezone.utc)
                return

            texts = [c["content"] for c in chunks]
            embeddings = await embed_chunks(texts)

            await delete_by_document(db, document.id)

            count = await insert_chunks(
                db,
                workspace_id=document.workspace_id,
                document_id=document.id,
                knowledge_base_id=document.knowledge_base_id,
                chunks=chunks,
                embeddings=embeddings,
            )

            document.status = "indexed"
            document.chunk_count = count
            document.last_indexed_at = datetime.now(timezone.utc)
            return

        # DROPBOX: fetch and concatenate text content from Dropbox files
        if document.source_type == "dropbox":
            from app.services.ingestion.extractors.dropbox_extractor import extract_from_dropbox

            parts: list[str] = []
            async for chunk in extract_from_dropbox(document.source_url or "", str(document.workspace_id), db):
                parts.append(chunk)
            content = "".join(parts)

            if not content.strip():
                document.status = "indexed"
                document.chunk_count = 0
                document.last_indexed_at = datetime.now(timezone.utc)
                return

            chunks = _chunk(document, content)

            if not chunks:
                document.status = "indexed"
                document.chunk_count = 0
                document.last_indexed_at = datetime.now(timezone.utc)
                return

            texts = [c["content"] for c in chunks]
            embeddings = await embed_chunks(texts)

            await delete_by_document(db, document.id)

            count = await insert_chunks(
                db,
                workspace_id=document.workspace_id,
                document_id=document.id,
                knowledge_base_id=document.knowledge_base_id,
                chunks=chunks,
                embeddings=embeddings,
            )

            document.status = "indexed"
            document.chunk_count = count
            document.last_indexed_at = datetime.now(timezone.utc)
            return

        # SALESFORCE: fan out to one child Document per Knowledge article
        if document.source_type == "salesforce":
            from app.services.ingestion.extractors.salesforce_extractor import extract_from_salesforce

            new_children: list[Document] = []
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
                new_children.append(child)

            await db.flush()  # assign IDs

            # Override source_type to "text" so _extract() reads raw_content
            for child in new_children:
                child.source_type = "text"
            await db.flush()
            child_ids = [str(child.id) for child in new_children]

            document.status = "indexed"
            document.chunk_count = len(new_children)
            document.last_indexed_at = datetime.now(timezone.utc)
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
                return
            from app.services.ingestion.extractors.zendesk_extractor import extract_from_zendesk

            new_children: list[Document] = []
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
                new_children.append(child)

            await db.flush()  # assign IDs

            # Override source_type to "text" so _extract() reads raw_content
            for child in new_children:
                child.source_type = "text"
            await db.flush()
            child_ids = [str(child.id) for child in new_children]

            document.status = "indexed"
            document.chunk_count = len(new_children)
            document.last_indexed_at = datetime.now(timezone.utc)
            await db.commit()

            # Ingest each article child asynchronously
            from app.workers.tasks.ingest_document import ingest_document

            for child_id in child_ids:
                ingest_document.delay(child_id)  # type: ignore[attr-defined]
            return

        content = _extract(document)
        chunks = _chunk(document, content)

        if not chunks:
            document.status = "indexed"
            document.chunk_count = 0
            document.last_indexed_at = datetime.now(timezone.utc)
            return

        texts = [c["content"] for c in chunks]
        embeddings = await embed_chunks(texts)

        await delete_by_document(db, document.id)

        count = await insert_chunks(
            db,
            workspace_id=document.workspace_id,
            document_id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            chunks=chunks,
            embeddings=embeddings,
        )

        document.status = "indexed"
        document.chunk_count = count
        document.last_indexed_at = datetime.now(timezone.utc)

    except Exception as e:
        logger.error(f"Ingestion failed for document {document_id}: {e}")
        document.status = "failed"
        raise


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
