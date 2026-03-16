import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TimestampUpdateMixin, UUIDPrimaryKeyMixin


class Chatbot(UUIDPrimaryKeyMixin, TimestampUpdateMixin, Base):
    __tablename__ = "chatbots"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str] = mapped_column(Text, server_default=text("'Assistant'"))
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone: Mapped[str] = mapped_column(Text, server_default=text("'professional'"))
    language: Mapped[str] = mapped_column(Text, server_default=text("'en'"))
    auto_detect_language: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    llm_provider: Mapped[str] = mapped_column(Text, server_default=text("'openrouter'"))
    llm_model: Mapped[str] = mapped_column(Text, server_default=text("'claude-haiku-4-5-20251001'"))
    byoak: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[float] = mapped_column(Float, server_default=text("0.3"))
    max_tokens: Mapped[int] = mapped_column(Integer, server_default=text("1000"))
    confidence_threshold: Mapped[float] = mapped_column(Float, server_default=text("0.65"))
    retrieval_top_k: Mapped[int] = mapped_column(Integer, server_default=text("5"))
    use_reranking: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))
    use_hybrid_retrieval: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))
    presales_kb_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    postsales_kb_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    fallback_type: Mapped[str] = mapped_column(Text, server_default=text("'escalate'"))
    fallback_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    widget_config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    brand_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_questions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    setup_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    setup_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_crawl_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crawl_jobs.id", ondelete="SET NULL"), nullable=True
    )
    active_crawl_job: Mapped["CrawlJob | None"] = relationship(
        "CrawlJob",
        foreign_keys=[active_crawl_job_id],
        lazy="select",
    )

    knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship(back_populates="chatbot")


class KnowledgeBase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_bases"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    chatbot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbots.id"), nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kb_type: Mapped[str] = mapped_column(Text, server_default=text("'general'"))

    chatbot: Mapped["Chatbot | None"] = relationship(back_populates="knowledge_bases")
    documents: Mapped[list["Document"]] = relationship(back_populates="knowledge_base")


class Document(UUIDPrimaryKeyMixin, TimestampUpdateMixin, Base):
    __tablename__ = "documents"

    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingestion_steps: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    char_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_frequency: Mapped[str] = mapped_column(Text, server_default=text("'weekly'"))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Chunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index("idx_chunks_document", "document_id"),
        Index("idx_chunks_kb", "knowledge_base_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    heading_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding = mapped_column(Vector(384), nullable=True)
    search_vector = mapped_column(TSVECTOR, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))

    document: Mapped["Document"] = relationship(back_populates="chunks")


class ArticleCollection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "article_collections"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("article_collections.id"), nullable=True
    )
    collection_type: Mapped[str] = mapped_column(Text, server_default=text("'collection'"))
    order_index: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    intercom_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    parent: Mapped["ArticleCollection | None"] = relationship(remote_side="ArticleCollection.id")


class Article(UUIDPrimaryKeyMixin, TimestampUpdateMixin, Base):
    __tablename__ = "articles"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    knowledge_base_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=True
    )
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("article_collections.id"), nullable=True
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(Text, server_default=text("'draft'"))
    is_ai_drafted: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    gap_cluster_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    views_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    helpful_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    not_helpful_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    parent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    intercom_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(Text, server_default=text("'en'"))
    order_index: Mapped[int] = mapped_column(Integer, server_default=text("0"))


class CrawlJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crawl_jobs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    kb_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False)
    root_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    pages_discovered: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    pages_queued: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    pages_failed: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    phase: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    include_paths: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    exclude_paths: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
