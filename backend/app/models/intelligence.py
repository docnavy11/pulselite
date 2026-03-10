import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
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
    query_embedding_model: Mapped[str] = mapped_column(Text, server_default=text("'text-embedding-3-small'"))
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
    gap_cluster_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class GapCluster(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gap_clusters"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    chatbot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbots.id"), nullable=True)
    topic_label: Mapped[str] = mapped_column(Text, nullable=False)
    topic_keywords: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    gap_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    representative_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    draft_article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_impact: Mapped[float | None] = mapped_column(Float, nullable=True)
    clustered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class IntelligenceSignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "intelligence_signals"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    signal_type: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    actioned: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    actioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))


class TopicCluster(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topic_clusters"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    chatbot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbots.id"), nullable=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    conversation_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    volume_trend: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    anomaly_detected: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    anomaly_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)


class LeadScore(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "lead_scores"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    tier: Mapped[str | None] = mapped_column(Text, nullable=True)
    signals: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    crm_pushed: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    crm_pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    slack_alerted: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


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
    lead_intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature_requests: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    bug_reports: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    competitor_mentions: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    expansion_signals: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    churn_signals: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    topics: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    customer_effort_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_items: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    llm_model: Mapped[str] = mapped_column(Text, server_default=text("'gpt-4o-mini'"))
    processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AutonomousResolutionStats(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "autonomous_resolution_stats"
    __table_args__ = (UniqueConstraint("workspace_id", "chatbot_id", "period_date"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    chatbot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chatbots.id"), nullable=True)
    period_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_conversations: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    autonomously_resolved: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    escalated_to_human: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    abandoned: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    avg_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    knowledge_velocity: Mapped[float | None] = mapped_column(Float, nullable=True)
    documentation_debt: Mapped[int | None] = mapped_column(Integer, nullable=True)
