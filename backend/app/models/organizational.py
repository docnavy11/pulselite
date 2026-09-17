import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TimestampUpdateMixin, UUIDPrimaryKeyMixin


class Workspace(UUIDPrimaryKeyMixin, TimestampUpdateMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(Text, server_default=text("'free'"))
    plan_conversation_cap: Mapped[int] = mapped_column(Integer, server_default=text("100"))
    timezone: Mapped[str] = mapped_column(Text, server_default=text("'UTC'"))
    primary_language: Mapped[str] = mapped_column(Text, server_default=text("'en'"))
    webhook_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    onboarding_step: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    stripe_customer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    credit_balance: Mapped[int] = mapped_column(Integer, server_default=text("1000"))
    auto_recharge_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    auto_recharge_threshold: Mapped[int] = mapped_column(Integer, server_default=text("200"))
    auto_recharge_amount: Mapped[int] = mapped_column(Integer, server_default=text("1000"))
    data_retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # None = retain forever
    openrouter_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    openrouter_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_models: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    internal_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_chatbot_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_byok: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)
    chars_indexed: Mapped[int] = mapped_column(BigInteger, server_default=text("0"), nullable=False)
    intelligence_config: Mapped[dict] = mapped_column(
        JSONB,
        server_default=text("""'{"auto_analyze": true, "sentiment_trends": true, "gap_clustering": true}'::jsonb"""),
        nullable=False,
    )
    last_report_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agents: Mapped[list["Agent"]] = relationship(back_populates="workspace")
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="workspace")


class Agent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("workspace_id", "email"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    two_fa_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="agents")
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="agent")


class WorkspaceMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspace_memberships"

    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'member'"))

    agent: Mapped["Agent"] = relationship(back_populates="memberships")
    workspace: Mapped["Workspace"] = relationship(back_populates="memberships")


class WorkspaceWebhook(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workspace_webhooks"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    event_types: Mapped[list] = mapped_column(
        JSONB, server_default=text('\'["conversation.created", "conversation.escalated"]\'::jsonb'), nullable=False
    )
    secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
