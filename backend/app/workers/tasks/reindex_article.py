import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import async_session_factory, engine
from app.models.knowledge import Article, Document
from app.services.ingestion.chunkers.markdown_chunker import chunk_markdown
from app.services.realtime import emit_to_workspace
from app.services.ingestion.embedder import embed_chunks
from app.services.ingestion.vector_store import delete_by_document, insert_chunks
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def reindex_article(self, article_id: str) -> dict:
    try:
        return asyncio.run(_reindex(uuid.UUID(article_id)))
    except Exception as exc:
        raise self.retry(exc=exc)  # type: ignore[attr-defined]


async def _reindex(article_id: uuid.UUID) -> dict:
    await engine.dispose()
    async with async_session_factory() as session:
        try:
            result = await session.execute(select(Article).where(Article.id == article_id))
            article = result.scalar_one_or_none()
            if article is None:
                logger.error(f"Article {article_id} not found")
                return {"status": "error", "detail": "Article not found"}

            if not article.body:
                return {"status": "skipped", "detail": "Article has no body content"}

            doc_result = await session.execute(
                select(Document).where(Document.metadata_.op("->>")("article_id") == str(article_id))
            )
            existing_doc = doc_result.scalar_one_or_none()

            if existing_doc:
                await delete_by_document(session, existing_doc.id)
                doc = existing_doc
                doc.raw_content = article.body
                doc.title = article.title
                doc.status = "processing"
                await emit_to_workspace(str(doc.workspace_id), "document:status_changed", {
                    "document_id": str(doc.id),
                    "knowledge_base_id": str(doc.knowledge_base_id),
                    "status": "processing",
                    "char_count": 0,
                    "title": doc.title or "",
                    "error_message": None,
                })
            else:
                doc = Document(
                    knowledge_base_id=article.knowledge_base_id,
                    workspace_id=article.workspace_id,
                    source_type="text",
                    raw_content=article.body,
                    title=article.title,
                    status="processing",
                    metadata_={"article_id": str(article_id), "source": "ai_draft"},
                )
                session.add(doc)
                await session.flush()

                await emit_to_workspace(str(doc.workspace_id), "document:status_changed", {
                    "document_id": str(doc.id),
                    "knowledge_base_id": str(doc.knowledge_base_id),
                    "status": "processing",
                    "char_count": 0,
                    "title": doc.title or "",
                    "error_message": None,
                })

            chunks = chunk_markdown(article.body)
            if not chunks:
                doc.status = "indexed"
                doc.chunk_count = 0
                doc.last_indexed_at = datetime.now(timezone.utc)
                await session.commit()

                await emit_to_workspace(str(doc.workspace_id), "document:status_changed", {
                    "document_id": str(doc.id),
                    "knowledge_base_id": str(doc.knowledge_base_id),
                    "status": "indexed",
                    "char_count": doc.char_count or 0,
                    "title": doc.title or "",
                    "error_message": None,
                })
                return {"status": "success", "chunks": 0}

            texts = [c["content"] for c in chunks]
            embeddings = await embed_chunks(texts)

            count = await insert_chunks(
                session,
                workspace_id=article.workspace_id,
                document_id=doc.id,
                knowledge_base_id=doc.knowledge_base_id,
                chunks=chunks,
                embeddings=embeddings,
            )

            doc.status = "indexed"
            doc.chunk_count = count
            doc.last_indexed_at = datetime.now(timezone.utc)

            await session.commit()

            await emit_to_workspace(str(doc.workspace_id), "document:status_changed", {
                "document_id": str(doc.id),
                "knowledge_base_id": str(doc.knowledge_base_id),
                "status": "indexed",
                "char_count": doc.char_count or 0,
                "title": doc.title or "",
                "error_message": None,
            })
            return {"status": "success", "chunks": count, "article_id": str(article_id)}
        except Exception:
            await session.rollback()
            raise
