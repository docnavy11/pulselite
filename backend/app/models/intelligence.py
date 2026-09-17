import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RetrievalLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "retrieval_logs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    chatbot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbots.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    retrieved_chunk_ids: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    reranked: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    escalated: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    response_generated: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))
    retrieval_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class GapEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gap_events"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    retrieval_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("retrieval_logs.id"), nullable=False
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    gap_cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gap_clusters.id"), nullable=True
    )


class GapCluster(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gap_clusters"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    chatbot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbots.id"), nullable=True)
    topic_label: Mapped[str] = mapped_column(Text, nullable=False)
    topic_keywords: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    gap_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    representative_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clustered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class ConversationAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation_analysis"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), unique=True, nullable=False
    )
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent_primary: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent_secondary: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    outcome_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    topics: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_model: Mapped[str] = mapped_column(Text, server_default=text("'claude-haiku-4-5-20251001'"))
    processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
