import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
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
    intercom_app_id: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    white_label_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)
    openrouter_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_models: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )

    agents: Mapped[list["Agent"]] = relationship(back_populates="workspace")
    teams: Mapped[list["Team"]] = relationship(back_populates="workspace")
    inboxes: Mapped[list["Inbox"]] = relationship(back_populates="workspace")
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="workspace")


class Agent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("workspace_id", "email"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_inbox_seat: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))
    availability: Mapped[str] = mapped_column(Text, server_default=text("'online'"))
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    two_fa_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="agents")
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="agent")


class Team(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teams"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="teams")
    members: Mapped[list["TeamMember"]] = relationship(back_populates="team")


class TeamMember(Base):
    __tablename__ = "team_members"

    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id"), primary_key=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), primary_key=True)
    priority_level: Mapped[int] = mapped_column(Integer, server_default=text("1"))

    team: Mapped["Team"] = relationship(back_populates="members")
    agent: Mapped["Agent"] = relationship()


class Inbox(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inboxes"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    channel_type: Mapped[str] = mapped_column(Text, server_default=text("'web_widget'"))
    channel_config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    is_inbox_seat_required: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))

    workspace: Mapped["Workspace"] = relationship(back_populates="inboxes")


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
